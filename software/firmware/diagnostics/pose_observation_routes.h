// HTTP handlers only queue acquisition or return immutable retained evidence.
#pragma once
#include "start_plan_structure.h"
namespace rocell_diag {
template<class Owner,class Server>
class PoseObservationRoutes {
 public:
  PoseObservationRoutes(Owner& owner,Server& server):owner_(owner),server_(server){}
  void register_routes(){
    if(registered_)return;registered_=true;
    server_.on("/rocell/pose/capture",HTTP_POST,[this](){
      no_cache();const auto body=server_.arg("plain");
      StrictPlanJson lexical;JsonDocument doc;
      if(body.length()==0||body.length()>384||!lexical.check(body.c_str(),body.length())||
         deserializeJson(doc,body.c_str(),body.length(),DeserializationOption::NestingLimit(2))){
        error(400,"INVALID_POSE_REQUEST");return;
      }
      static const char* const fields[]={"boot_id","scan_id"};
      const auto root=doc.template as<JsonVariantConst>();
      if(!plan_fields(root,fields,2)||!root["boot_id"].is<const char*>()||!root["scan_id"].is<const char*>()){
        error(400,"INVALID_POSE_REQUEST");return;
      }
      if(!owner_.request(root["boot_id"].as<const char*>(),root["scan_id"].as<const char*>())){
        error(409,"POSE_NOT_ADMITTED");return;
      }
      server_.send(202,"application/json","{\"status\":\"POSE_QUEUED\",\"retry_allowed\":false}");
    });
    server_.on("/rocell/pose/record",HTTP_GET,[this](){
      no_cache();
      if(server_.args()!=1){error(400,"INVALID_INDEX");return;}
      const auto index=server_.arg("index");
      if(index.length()!=1||index[0]<'0'||index[0]>'3'){error(400,"INVALID_INDEX");return;}
      if(owner_.active()){error(409,"POSE_ACTIVE");return;}
      if(owner_.export_fault()){error(500,"POSE_EXPORT_FAILED");return;}
      const char* record=owner_.record(size_t(index[0]-'0'));
      if(!record){error(404,"POSE_RECORD_UNAVAILABLE");return;}
      server_.send(200,"application/json",record);
    });
  }
 private:
  void no_cache(){server_.sendHeader("Cache-Control","no-store");}
  void error(int code,const char* reason){char text[96];
    snprintf(text,sizeof(text),"{\"error\":\"%s\"}",reason);server_.send(code,"application/json",text);}
  Owner& owner_;Server& server_;bool registered_=false;
};
}
