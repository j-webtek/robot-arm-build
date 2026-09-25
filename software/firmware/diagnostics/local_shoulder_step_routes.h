// Same-task transport adapter. Access must return the reserved board-owned
// session. No bus is available in a handler; all acquisition/dispatch is polled.
#pragma once
#include "local_shoulder_step_session.h"
namespace rocell_diag {
template<class Access,class Clock,class Web> class LocalShoulderStepRoutes {
 public:
  LocalShoulderStepRoutes(Access& access,Clock& clock,Web& web):access_(access),clock_(clock),web_(web){}
  void register_routes(){
    if(registered_)return;registered_=true;
    web_.on("/rocell/local-step/status",HTTP_GET,[this](){
      if(web_.args()){send(400,"{}");return;}auto* s=access_();if(!s){send(409,"{}");return;}
      JsonDocument doc;doc["schema"]="rocell.local_step_status.v1";
      doc["boot_id"]=s->boot_id();doc["command_id"]=s->command_id();
      const char* states[]={"CAPTURE","WAITING_EXPORT","AUTHORIZATION","INTENT","WRITE","OBSERVE","COMPLETE","FAULT"};
      doc["state"]=states[unsigned(s->local_phase())];doc["sequence"]=s->sequence();
      doc["target_packets"]=s->writes();doc["record_available"]=s->record()!=nullptr;
      doc["reason"]=s->reason();doc["controller_now_us"]=clock_.now_us();
      if(!hold_json_finish(doc,response_,sizeof(response_))){send(500,"{}");return;}send(200,response_);
    });
    web_.on("/rocell/local-step/record",HTTP_GET,[this](){
      if(web_.args()){send(400,"{}");return;}auto* s=access_();if(!s){send(409,"{}");return;}
      if(!s->record()){send(404,"{}");return;}send(200,s->record());
    });
    web_.on("/rocell/local-step/authorize",HTTP_POST,[this](){accept(true);});
    web_.on("/rocell/local-step/receipt",HTTP_POST,[this](){accept(false);});
  }
 private:
  void accept(bool authorize){
    if(web_.args()!=1||web_.argName(0)!="plain"){send(400,"{}");return;}
    auto* s=access_();if(!s){send(409,"{}");return;}
    if(s->local_phase()!=(authorize?LocalStepPhase::Authorization:LocalStepPhase::Waiting)){send(409,"{}");return;}
    const auto body=web_.arg("plain");
    if(body.length()==0||body.length()%2||body.length()>sizeof(token_)*2||(!authorize&&body.length()!=248)){
      send(400,"{}");return;
    }
    for(unsigned i=0;i<body.length();++i){
      char c=body[i];int n=c>='0'&&c<='9'?c-'0':c>='a'&&c<='f'?c-'a'+10:-1;
      if(n<0){memset(token_,0,sizeof(token_));send(400,"{}");return;}
      if(i%2==0)token_[i/2]=n<<4;else token_[i/2]|=n;
    }
    const auto now=clock_.now_us();
    bool ok=authorize?s->authorize(token_,body.length()/2,now):s->receipt({token_,body.length()/2},now);
    memset(token_,0,sizeof(token_));
    send(ok?200:409,ok?"{\"accepted\":true,\"movement_performed_by_handler\":false}":"{\"accepted\":false}");
  }
  void send(int code,const char* raw){web_.sendHeader("Cache-Control","no-store");web_.send(code,"application/json",raw);}
  Access& access_;Clock& clock_;Web& web_;bool registered_=false;
  uint8_t token_[2200]={};char response_[1024]={};
};
}
