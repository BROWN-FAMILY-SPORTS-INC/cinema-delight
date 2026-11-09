-- List installed native plugins and their control ports:  ardour9-lua tools/ardour/plugins.lua <session dir> <name> [filter]
assert(load_session(arg[1],arg[2]))
for p in ARDOUR.LuaAPI.list_plugins():iter() do
 if (not arg[3] or string.find(p.name,arg[3])) and (p.type==ARDOUR.PluginType.LV2 or p.type==ARDOUR.PluginType.Lua) then
  print(p.name,p.unique_id,p.type)
  if arg[3] then
   local proc=ARDOUR.LuaAPI.new_plugin(Session,p.type==ARDOUR.PluginType.Lua and p.name or p.unique_id,p.type,"")
   assert(not proc:isnil())
   local plug=proc:to_plugininsert():plugin(0)
   for i=0,plug:parameter_count()-1 do
    if plug:parameter_is_control(i) then print(i,plug:parameter_label(i),plug:get_parameter(i)) end
   end
  end
 end
end
