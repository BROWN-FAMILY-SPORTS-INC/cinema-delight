"""The cleanup pass: stereo audio in, an editable Ardour session and a native offline bounce out.

    python3 tools/ardour.py <stems.json> --session <new dir> --bounce <out.wav> [--desk <desk.json>]

Use it for two jobs. Finishing a song: the picked option's stems (or its one stereo mix) get EQ,
compression and levels. Salvaging a recording: a narration or a demo's captured sound gets its rumble
cut, its noise and peaks tamed, and its level set. Either way the session stays editable in Ardour,
so a person or a later pass can open it and change anything.

stems.json:  {"rate": 48000, "seconds": 30, "parts": [{"name": "voice", "file": "voice.wav", "at": 0, "gain_db": 0}]}
             every file stereo; `at` is where it starts, in seconds
desk.json:   {"gain": 0, "levels": {"voice": -3}, "pans": {}, "inserts": [{"tracks": "voice", "plugin": "compressor",
             "params": {"ratio": 3, "threshold": -18}}], "master": [...], "buses": [...], "sends": [...],
             "outputs": [...], "automation": [...]}
             `compressor` and `eq_7band` are named shortcuts for Ardour's own a-comp and a-eq; any installed LV2
             plugin by URI or Lua plugin by name works with its control labels or indices
             (list them: ardour9-lua tools/ardour/plugins.lua <session dir> Studio <filter>).

Requires Ardour 9 (ardour9-lua, ardour9-export), ffmpeg and ffprobe. No GUI or sound device. The session
is built in a temporary folder beside the target and moved into place only when the bounce checks out,
so a failed build never replaces a good one. Last line of output is JSON.
"""
import argparse
import copy
import fnmatch
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

DRIVER = Path(__file__).with_name("ardour") / "session.lua"
SLOTS = "abcdefghijklmnopqrstuvwxyz"
CLOCK = 282240000


# Ardour starts a thread to load MIDI name files, and its Lua runner cancels every thread at exit; the loader swallows
# the cancellation in a catch(...) and glibc aborts ("FATAL: exception not rethrown"). These renders never use MIDI
# names, so the loader is switched off: 20 of 20 quick exits clean, against 10 of 20 without it, on a loaded machine.
ARDOUR_ENV = {**os.environ, "ARDOUR_NO_PATCHFILES": "1"}


def run(args, allow=()):
    result = subprocess.run(list(map(str, args)), capture_output=True, text=True,
                            env=ARDOUR_ENV if str(args[0]).startswith("ardour") else None)
    if result.returncode and result.returncode not in allow:
        raise RuntimeError(f"{args[0]} failed ({result.returncode}):\n{result.stdout[-4000:]}\n{result.stderr[-4000:]}")
    return result.stdout if not allow else (result.returncode, result.stdout)


def wav_frames(path):
    """The frames and channels a WAV's header declares, or None when the header was never finished. A writer that
    dies before closing the file leaves a placeholder size, which this refuses rather than estimating from the file."""
    with open(path, "rb") as f:
        data = f.read(1 << 16)
        size = os.path.getsize(path)
    if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        return None
    i, channels, bits = 12, None, None
    while i + 8 <= len(data):
        cid, n = data[i:i + 4], int.from_bytes(data[i + 4:i + 8], "little")
        if cid == b"fmt ":
            channels = int.from_bytes(data[i + 10:i + 12], "little")
            bits = int.from_bytes(data[i + 22:i + 24], "little")
        elif cid == b"data":
            if not channels or not bits or n in (0, 0xFFFFFFFF) or i + 8 + n > size:
                return None
            return n // (channels * bits // 8), channels
        i += 8 + n + (n & 1)
    return None


def lua(value):
    """Serialize data, never interpolate it as executable Lua."""
    if value is None:
        return "nil"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        if not math.isfinite(value):
            raise ValueError("Nonfinite number in desk")
        return repr(value)
    if isinstance(value, str):
        # Lua quoted strings support decimal byte escapes, unlike JSON's unicode escapes.
        return '"' + "".join(f"\\{ord(c):03d}" if ord(c)<32 or c in '\\"' else c for c in value) + '"'
    if isinstance(value, list):
        return "{" + ",".join(lua(v) for v in value) + "}"
    if isinstance(value, dict):
        return "{" + ",".join("[" + lua(str(k)) + "]=" + lua(v) for k,v in value.items()) + "}"
    raise TypeError(type(value))


def finite(value, label):
    n = float(value)
    if not math.isfinite(n):
        raise ValueError(f"{label} must be finite")
    return n


def plugin(spec, slot):
    """Resolve supported desk aliases; native plugins use exact control labels or indices."""
    spec = copy.deepcopy(spec)
    unknown=set(spec)-{"plugin","type","params","slot","tracks"}
    if unknown: raise ValueError(f"Unknown insert fields: {sorted(unknown)}")
    if spec.get("type","lv2") not in ("lv2","lua"): raise ValueError("Plugin type must be lv2 or lua")
    name, params = spec["plugin"], spec.get("params", {})
    out = {"plugin": name, "type": spec.get("type", "lv2"), "params": params, "slot": spec.get("slot", slot)}
    if name == "compressor":
        mapping = {"attack":0,"release":1,"knee":2,"ratio":3,"threshold":4,"makeup":5}
        unknown = set(params)-mapping.keys()
        if unknown: raise ValueError(f"Unsupported compressor parameters: {sorted(unknown)}")
        out["params"] = {str(mapping[k]):v for k,v in params.items()}
        out["aliases"] = mapping
        out["plugin"] = "urn:ardour:a-comp#stereo"
    elif name == "eq_7band":
        mapping = {"low_shelf_freq":0,"low_shelf_gain":1,"low_mid_freq":2,"low_mid_gain":3,
                   "mid_freq":5,"mid_gain":6,"high_mid_freq":8,"high_mid_gain":9,
                   "presence_freq":11,"presence_gain":12,"high_shelf_freq":14,"high_shelf_gain":15}
        unknown = set(params)-set(mapping)-{"low_mid_q","mid_q","high_mid_q","presence_q","hpf_on","hpf_freq","hpf_slope","lpf_on","lpf_freq","lpf_slope"}
        if unknown: raise ValueError(f"Unsupported EQ parameters: {sorted(unknown)}")
        out["params"] = {str(mapping[k]):v for k,v in params.items() if k in mapping}
        for prefix,port in [("low_mid",4),("mid",7),("high_mid",10),("presence",13)]:
            if prefix+"_q" in params:
                q = finite(params[prefix+"_q"],"EQ Q")
                if q<=0: raise ValueError("EQ Q must be positive")
                out["params"][str(port)] = 2*math.asinh(1/(2*q))/math.log(2)
        out["plugin"] = "urn:ardour:a-eq"
        out["aliases"] = mapping
        filters = {}
        if params.get("hpf_on"):
            filters.update({"High Pass Cut off frequency":params.get("hpf_freq",100),"High Pass Steepness":params.get("hpf_slope",1)})
        if params.get("lpf_on"):
            filters.update({"Low Pass Cut off frequency":params.get("lpf_freq",18000),"Low Pass Steepness":params.get("lpf_slope",1)})
        if filters:
            filters.setdefault("High Pass Steepness",0)
            filters.setdefault("Low Pass Steepness",0)
            return [dict(plugin="ACE High/Low Pass Filter",type="lua",params=filters,slot=out["slot"]+"-filters"),out]
    elif not (name.startswith(("urn:","http:","https:")) or out["type"]=="lua"):
        raise ValueError(f"plugin {name!r} is not a shortcut, an LV2 URI or a Lua plugin name; nothing was dropped")
    return [out]


def routes_for(manifest, desk):
    names = [p["name"] for p in manifest["parts"]]
    buses = desk.get("buses", [])
    all_names = names + [b["name"] for b in buses] + ["master"]
    if len(set(all_names)) != len(all_names) or "Master" in all_names:
        raise ValueError("Track and bus names must be unique; Master/master are reserved")
    routes = {n:{"name":n,"gain_db":float(desk.get("gain",0)) if n in names else 0,"inserts":[]} for n in all_names}
    for part in manifest["parts"]:
        routes[part["name"]]["gain_db"] += float(part.get("gain_db",0))
        if part.get("output"): routes[part["name"]]["output"]=part["output"]
    def select(selector):
        patterns = [selector] if isinstance(selector,str) else selector
        chosen = [n for n in names if any(fnmatch.fnmatchcase(n,s) for s in patterns)]
        if not chosen: raise ValueError(f"No tracks match {selector!r}")
        return chosen
    logical_slots={n:0 for n in all_names}
    def add(name, ins):
        number=logical_slots[name]
        if not ins.get("slot") and number>=len(SLOTS): raise ValueError("Name the insert slot for chains longer than 26 inserts")
        slot = ins.get("slot") or SLOTS[number]
        if any(p["slot"]==slot for p in routes[name]["inserts"]): raise ValueError(f"Duplicate insert slot {name}:{slot}")
        item={**ins,"slot":slot}
        routes[name]["inserts"] += plugin(item,slot)
        logical_slots[name]+=1
    for b in buses:
        routes[b["name"]]["gain_db"] = b.get("level_db",0)
        if b.get("output"): routes[b["name"]]["output"]=b["output"]
        for ins in b.get("inserts",[]): add(b["name"],ins)
    for ins in desk.get("inserts",[]):
        for name in select(ins["tracks"]): add(name,ins)
    for ins in desk.get("master",[]): add("master",ins)
    for n,v in desk.get("levels",{}).items():
        if n not in routes: raise ValueError(f"Unknown level track {n}")
        routes[n]["gain_db"]=v
    for n,v in desk.get("pans",{}).items():
        if n not in routes: raise ValueError(f"Unknown panned track {n}")
        routes[n]["pan"]=v
    for item in desk.get("outputs",[]):
        for n in select(item["tracks"]): routes[n]["output"]=item["bus"]
    sends = []
    for s in desk.get("sends",[]):
        if s["bus"] not in routes or s["bus"] in names: raise ValueError(f"Unknown send bus {s['bus']}")
        for n in select(s["tracks"]): sends.append({"track":n,"bus":s["bus"],"db":finite(s.get("db",0),"send gain")})
    for r in routes.values():
        finite(r["gain_db"],"gain")
        if "pan" in r and not -1<=finite(r["pan"],"pan")<=1: raise ValueError("Pan must be -1..1")
        if r.get("output") not in (None,*[b["name"] for b in buses],"master"): raise ValueError("Unknown output bus")
        for ins in r["inserts"]:
            for v in ins["params"].values(): finite(v,"plugin parameter")
    # Reject routing cycles before creating a session.
    for n in routes:
        seen = set()
        while n!="master":
            if n in seen: raise ValueError("Audio routing cycle")
            seen.add(n)
            n = routes[n].get("output","master")
    automation = desk.get("automation",[])
    for a in automation:
        if a["track"] not in routes: raise ValueError(f"Unknown automated track {a['track']}")
        last = -1
        for p in a["points"]:
            at = finite(p["at"],"automation time")
            if at<0 or at<=last: raise ValueError("Automation times must increase from zero")
            last=at
            finite(p["value"],"automation value")
    return list(routes.values()),sends


def timeline(manifest,take):
    markers=list(manifest.get("markers",[]))
    for field,at,label in [("sections","t0","name"),("moments","t","words"),("screen","t","words")]:
        markers += [{"at":v[at],"name":str(v.get(label,field))} for v in take.get(field,[]) if v.get(at) is not None]
    tempos=[]
    meters=[]
    if manifest.get("tempo") is not None:
        tempos=[{"at":0,"bpm":finite(manifest["tempo"],"tempo")}]
    bars,beats=take.get("bars",[]),take.get("bar_beats")
    for i,(start,end) in enumerate(zip(bars,bars[1:])):
        n=(beats[i+1]-beats[i]) if isinstance(beats,list) and i+1<len(beats) else beats if isinstance(beats,(int,float)) else None
        if n is None or end<=start: continue
        bpm=60*n*(.5 if take.get("beat")=="eighth" else 1)/(end-start)
        if not tempos or abs(tempos[-1]["bpm"]-bpm)>.05: tempos.append({"at":start,"bpm":bpm})
        if float(n).is_integer():
            meter={"at":start,"numerator":int(n),"denominator":8 if take.get("beat")=="eighth" else 4}
            if not meters or (meters[-1]["numerator"],meters[-1]["denominator"])!=(meter["numerator"],meter["denominator"]): meters.append(meter)
    meter=manifest.get("meter",take.get("meter"))
    if not meters and isinstance(meter,str) and re.fullmatch(r"\d+/\d+",meter):
        num,den=map(int,meter.split("/"))
        meters=[{"at":0,"numerator":num,"denominator":den}]
    if any(t["bpm"]<=0 for t in tempos) or any(m["numerator"]<=0 or m["denominator"]<=0 for m in meters):
        raise ValueError("Tempo and meter must be positive")
    return markers,tempos,meters


def prepare(stems_path, desk=None, take=None):
    path = Path(stems_path).resolve()
    if path.is_dir(): path /= "stems.json"
    manifest = json.loads(path.read_text())
    desk = copy.deepcopy(desk or {})
    unknown = set(desk)-{"gain","levels","inserts","master","buses","sends","outputs","pans","automation"}
    if unknown:
        raise ValueError(f"Unknown desk fields {sorted(unknown)}; nothing was run")
    if not manifest.get("parts"): raise ValueError("The stem manifest needs at least one part")
    rate = int(manifest["rate"])
    if rate not in (44100,48000,88200,96000): raise ValueError("Unsupported session sample rate")
    tracks=[]
    for p in manifest["parts"]:
        source = (path.parent/p["file"]).resolve()
        if not source.is_file(): raise ValueError(f"Missing stem {source}")
        info=json.loads(run(["ffprobe","-v","error","-select_streams","a:0","-show_entries","stream=sample_rate,channels,duration","-of","json",source]))["streams"][0]
        if int(info["channels"])!=2: raise ValueError(f"Stem must be stereo: {source}")
        duration=finite(info["duration"],"source duration")
        at=finite(p.get("at",0),"track position")
        if at<0 or duration<=0: raise ValueError("Invalid stem extent")
        tracks.append({**p,"file":str(source),"at":at,"source_seconds":duration})
    seconds = finite(manifest["seconds"],"session duration")
    if seconds<=0: raise ValueError("Session duration must be positive")
    routes,sends = routes_for(manifest,desk)
    markers,tempos,meters=timeline(manifest,take or {})
    return {"name":"Studio","rate":rate,"seconds":seconds,"tracks":tracks,"buses":desk.get("buses",[]),"routes":routes,"sends":sends,"automation":desk.get("automation",[]),"markers":markers,"tempos":tempos,"meters":meters}


def attach(session, cfg):
    state=session/"Studio.ardour"
    tree=ET.parse(state)
    root=tree.getroot()
    sources=root.find("Sources")
    audio=session/"interchange/Studio/audiofiles"
    audio.mkdir(parents=True,exist_ok=True)
    counter=max(10000,int(root.get("id-counter")))
    def uid():
        nonlocal counter
        counter+=1
        return str(counter)
    def stamp(seconds): return "a"+str(round(seconds*CLOCK))
    playlists={p.get("orig-track-id"):p for p in root.findall("./Playlists/Playlist")}
    for i,t in enumerate(cfg["tracks"]):
        dest=audio/f"{i+1:02d}-{re.sub('[^a-zA-Z0-9_-]','-',t['name'])}.wav"
        # Keep float headroom. No pre-fader clipping workaround is needed in Ardour.
        run(["ffmpeg","-v","error","-y","-i",t["file"],"-ar",cfg["rate"],"-c:a","pcm_f32le",dest])
        ids=[]
        for ch in range(2):
            id=uid(); ids.append(id)
            ET.SubElement(sources,"Source",{"name":dest.name,"type":"audio","flags":"","id":id,"channel":str(ch),"origin":"","natural-position":"0"})
        route=next(r for r in root.findall("./Routes/Route") if r.get("name")==t["name"])
        playlist=playlists[route.get("id")]
        attrs={"id":uid(),"name":t["name"],"type":"audio","start":"a0","length":stamp(t["source_seconds"])+"@"+stamp(t["at"]),"whole-file":"0","muted":"0","opaque":"1","scale-amplitude":"1","channels":"2","first-edit":"nothing","layering-index":"0","fade-in-active":"0","fade-out-active":"0"}
        for ch,id in enumerate(ids): attrs.update({f"source-{ch}":id,f"master-source-{ch}":id})
        ET.SubElement(playlist,"Region",attrs)
    locations=root.find("Locations")
    ET.SubElement(locations,"Location",{"id":uid(),"name":"session","start":"a0","end":stamp(cfg["seconds"]),"flags":"IsSessionRange","locked":"0"})
    for mark in cfg["markers"]:
        at=stamp(finite(mark["at"],"marker position"))
        ET.SubElement(locations,"Location",{"id":uid(),"name":str(mark["name"]),"start":at,"end":at,"flags":"IsMark","locked":"0"})
    for option in root.findall("./Config/Option"):
        if option.get("name")=="default-time-domain": option.set("value","AudioTime")
    root.set("id-counter",str(counter))
    ET.indent(tree)
    tree.write(state,encoding="UTF-8",xml_declaration=True)


def render(stems_path, session_dir, bounce, desk=None, take=None):
    for binary in ("ardour9-lua","ardour9-export","ffmpeg","ffprobe"):
        if not shutil.which(binary): raise RuntimeError(f"Required production tool is missing: {binary}")
    cfg=prepare(stems_path,desk,take)
    target=Path(session_dir).resolve()
    bounce=Path(bounce).resolve()
    if target.exists(): raise ValueError(f"Session directory already exists: {target}. Choose a fresh render folder.")
    target.parent.mkdir(parents=True,exist_ok=True)
    # Render in isolation. A failed build never replaces the previous good session or bounce.
    with tempfile.TemporaryDirectory(prefix=".ardour-",dir=target.parent) as temp:
        session=Path(temp)/"Studio"
        cfg["session_dir"]=str(session)
        config=Path(temp)/"desk.lua"
        config.write_text("return "+lua(cfg)+"\n")
        for mode in ("create","mix"):
            if mode=="mix": attach(session,cfg)
            output=run(["ardour9-lua",DRIVER,config,mode])
            if "STUDIO_SAVED" not in output: raise RuntimeError("Ardour did not confirm the saved session")
        rendered=Path(temp)/"bounce.wav"
        code,_=run(["ardour9-export","-b","float","-o",rendered,session,"Studio"],allow=(-11,))
        if code==-11:
            # Ardour 9.8's exporter can crash in its butler thread while tearing the session down after the bounce is
            # written. Keep the bounce only if its header declares every frame; a half-written file never passes.
            head=wav_frames(rendered) if rendered.exists() else None
            if not head or head[1]!=2 or abs(head[0]-round(cfg["seconds"]*cfg["rate"]))>2:
                raise RuntimeError(f"ardour9-export crashed (-11) before the bounce was complete: header {head}")
        info=json.loads(run(["ffprobe","-v","error","-select_streams","a:0","-show_entries","stream=duration,channels,sample_rate","-of","json",rendered]))["streams"][0]
        if abs(float(info["duration"])-cfg["seconds"])>2/cfg["rate"] or int(info["channels"])!=2: raise RuntimeError("Ardour bounce extent/channel mismatch")
        cfg["session_dir"]="."
        (session/"studio-desk.json").write_text(json.dumps(cfg,indent=2)+"\n")
        shutil.move(session,target)
        bounce.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(rendered,bounce)
    return target/"Studio.ardour"


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("stems")
    p.add_argument("--session",required=True)
    p.add_argument("--bounce",required=True)
    p.add_argument("--desk")
    a=p.parse_args()
    try:
        desk=json.loads(Path(a.desk).read_text()) if a.desk else {}
        state=render(a.stems,a.session,a.bounce,desk,{})
        print(json.dumps({"ok":True,"wrote":[str(state),str(Path(a.bounce).resolve())],"problems":[]}))
    except (ValueError,RuntimeError) as e:
        print(json.dumps({"ok":False,"wrote":[],"problems":[str(e)]}))
        raise SystemExit(1)
