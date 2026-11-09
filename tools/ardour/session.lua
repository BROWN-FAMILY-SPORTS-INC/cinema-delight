-- Shared native Ardour driver. The Python adapter supplies a validated Lua table.
local cfg=dofile(arg[1])
if arg[2]=="create" then
 assert(create_session(cfg.session_dir,cfg.name,cfg.rate),"Cannot create Ardour session")
 for _,t in ipairs(cfg.tracks) do
  Session:new_audio_track(2,2,ARDOUR.RouteGroup(),1,t.name,4294967295,ARDOUR.TrackMode.Normal,false,false)
 end
 for _,b in ipairs(cfg.buses) do
  Session:new_audio_route(2,2,ARDOUR.RouteGroup(),1,b.name,ARDOUR.PresentationInfo.Flag.AudioBus,4294967295)
 end
else
 assert(load_session(cfg.session_dir,cfg.name),"Cannot reopen Ardour session")
 if #cfg.tempos>0 or #cfg.meters>0 then
  local tm=Temporal.TempoMap.write_copy()
  for _,p in ipairs(cfg.tempos) do tm:set_tempo(Temporal.Tempo(p.bpm,p.bpm,4),Temporal.timepos_t(math.floor(p.at*cfg.rate+.5))) end
  for _,p in ipairs(cfg.meters) do tm:set_meter(Temporal.Meter(p.numerator,p.denominator),Temporal.timepos_t(math.floor(p.at*cfg.rate+.5))) end
  Temporal.TempoMap.update(tm)
 end
 local function route(name)
  local r=name=="master" and Session:master_out() or Session:route_by_name(name)
  assert(not r:isnil(),"Missing route "..name)
  return r
 end
 local function fader_index(r)
  local amps=0
  for i=0,200 do
   local p=r:nth_processor(i)
   assert(not p:isnil(),"Missing fader")
   -- Newly-created Ardour routes have trim then fader, both named Amp.
   if p:name()=="Amp" then amps=amps+1; if amps==2 then return i end end
  end
  error("Too many processors")
 end
 local function connect(out,into)
  for c=0,1 do assert(out:audio(c):connect(into:audio(c):name())==0,"Cannot connect audio ports") end
 end
 local function automation(ac,points,kind)
  assert(not ac:isnil(),"Missing automation control")
  local al=ac:alist()
  for _,p in ipairs(points) do
   local value=p.value
   if kind=="volume" then value=10^(value/20) elseif kind=="pan" then value=(value+1)/2 end
   al:add(Temporal.timepos_t(math.floor(p.at*cfg.rate+.5)),value,false,true)
  end
  ac:set_automation_state(ARDOUR.AutoState.Play)
 end
 local inserted={}
 for _,t in ipairs(cfg.routes) do
  local r=route(t.name)
  if t.gain_db then r:gain_control():set_value(10^(t.gain_db/20),PBD.GroupControlDisposition.NoGroup) end
  if t.pan then r:pan_azimuth_control():set_value((t.pan+1)/2,PBD.GroupControlDisposition.NoGroup) end
  inserted[t.name]={}
  for _,ins in ipairs(t.inserts) do
   local typ=ins.type=="lua" and ARDOUR.PluginType.Lua or ARDOUR.PluginType.LV2
   local p=ARDOUR.LuaAPI.new_plugin(Session,ins.plugin,typ,"")
   assert(not p:isnil(),"Unavailable plugin "..ins.plugin)
   assert(r:add_processor_by_index(p,fader_index(r),nil,true)==0,"Cannot insert "..ins.plugin)
   local plug=p:to_plugininsert():plugin(0)
   -- A desk names a parameter by its label or by its control number: the nth control port, inputs and outputs
   -- counted together, which is what LuaAPI.set_processor_param and plugin_automation take. get_parameter and
   -- Evoral.Parameter take the port itself. The two agree only when a plugin lists its controls before its audio
   -- (ACE EQ, ACE Compressor); ACE Reverb lists audio first, so its labels used to reach the wrong control.
   local ports,portof={},{}
   local n=0
   for i=0,plug:parameter_count()-1 do
    if plug:parameter_is_control(i) then
     if plug:parameter_is_input(i) then ports[plug:parameter_label(i)]=n end
     portof[n]=i
     n=n+1
    end
   end
   for alias,port in pairs(ins.aliases or {}) do ports[alias]=port end
   for key,value in pairs(ins.params) do
    local port=tonumber(key) or ports[key]
    assert(port and portof[port],"Unknown parameter "..key.." for "..ins.plugin)
    assert(ARDOUR.LuaAPI.set_processor_param(p,port,value),"Cannot set parameter "..key)
    assert(math.abs(plug:get_parameter(portof[port])-value)<=math.max(.0001,math.abs(value)*.00001),"Parameter clamped or invalid: "..key)
   end
   inserted[t.name][ins.slot]={processor=p,ports=ports,portof=portof}
   print("INSERT",t.name,ins.plugin)
  end
 end
 for _,t in ipairs(cfg.routes) do
  local r=route(t.name)
  if t.output then
   assert(r:output():disconnect_all()==0,"Cannot disconnect route")
   connect(r:output(),route(t.output):input())
  end
 end
 for _,s in ipairs(cfg.sends) do
  local r=route(s.track)
  local before=r:main_outs()
  local proc=ARDOUR.LuaAPI.new_send(Session,r,before)
  assert(not proc:isnil(),"Cannot create send")
  local send=proc:to_send()
  connect(send:output(),route(s.bus):input())
  send:gain_control():set_value(10^(s.db/20),PBD.GroupControlDisposition.NoGroup)
 end
 for _,a in ipairs(cfg.automation) do
  local r=route(a.track)
  if a.param=="volume" then automation(r:gain_control(),a.points,"volume")
  elseif a.param=="pan" then automation(r:pan_azimuth_control(),a.points,"pan")
  else
   local slot,key=string.match(a.param,"^plugin:([^:]+):(.+)$")
   local entry=inserted[a.track][slot]
   assert(entry,"Missing automated insert "..a.param)
   local port=tonumber(key) or entry.ports[key]
   assert(port and entry.portof[port],"Unknown automated parameter "..a.param)
   local al,cl,pd=ARDOUR.LuaAPI.plugin_automation(entry.processor,port)
   assert(not al:isnil(),"Cannot automate plugin")
   for _,p in ipairs(a.points) do
    assert(p.value>=pd.lower and p.value<=pd.upper,"Plugin automation is out of range")
    cl:add(Temporal.timepos_t(math.floor(p.at*cfg.rate+.5)),p.value,false,true)
   end
   local control=entry.processor:to_automatable():automation_control(Evoral.Parameter(ARDOUR.AutomationType.PluginAutomation,0,entry.portof[port]),true)
   assert(not control:isnil(),"Missing plugin automation control")
   control:set_automation_state(ARDOUR.AutoState.Play)
  end
 end
end
assert(Session:save_state("",false,false,false,false,false)==0,"Session save failed")
print("STUDIO_SAVED",cfg.name)
close_session()
-- The MIDI name-file loader that once raced this exit is switched off by tools/ardour.py (ARDOUR_NO_PATCHFILES).
