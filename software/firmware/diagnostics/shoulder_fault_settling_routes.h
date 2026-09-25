// Candidate routes only: caller must provide the authorized faulted owner's
// collector. Handlers have no bus reference; advance() runs on the control task.
#pragma once
#include "shoulder_fault_settling_session.h"
namespace rocell_diag {
template<class Access,class Clock,class Web> class ShoulderFaultSettlingRoutes {
 public:
  ShoulderFaultSettlingRoutes(Access& access,Clock& clock,Web& web):access_(access),clock_(clock),web_(web){}
  void register_routes(){
    if(registered_)return;registered_=true;
    web_.on("/rocell/shoulder-settling/status",HTTP_GET,[this](){
      if(web_.args()!=0){send(400,"{\"error\":\"NO_PARAMETERS_ALLOWED\"}");return;}
      auto* s=access_();if(!s){missing();return;}
      JsonDocument doc;doc["schema"]="rocell.shoulder_settling_status.v1";
      doc["boot_id"]=s->boot_id();doc["command_id"]=s->command_id();doc["count"]=s->count();
      const char* states[]={"IDLE","READING","WAITING_EXPORT","SETTLED","EXHAUSTED","FAILED"};
      doc["state"]=states[static_cast<unsigned>(s->state())];doc["reason"]=s->reason();
      doc["parent_fault_latched"]=true;doc["movement_authorized"]=false;
      doc["record_available"]=s->record()!=nullptr;
      if(!hold_json_finish(doc,response_,sizeof(response_))){send(500,"{}");return;}
      send(200,response_);
    });
    web_.on("/rocell/shoulder-settling/record",HTTP_GET,[this](){
      if(web_.args()!=0){send(400,"{}");return;}
      auto* s=access_();if(!s){missing();return;}
      if(!s->record()){send(404,"{\"error\":\"NO_RECORD\"}");return;}
      send(200,s->record());
    });
    web_.on("/rocell/shoulder-settling/start",HTTP_POST,[this](){accept(true);});
    web_.on("/rocell/shoulder-settling/receipt",HTTP_POST,[this](){accept(false);});
  }
 private:
  void accept(bool start){
    if(web_.args()!=1||web_.argName(0)!="plain"){send(400,"{}");return;}
    auto* s=access_();if(!s){missing();return;}
    if(s->state()!=(start?SettlingState::Idle:SettlingState::WaitingExport)){send(409,"{}");return;}
    const auto body=web_.arg("plain");if(body.length()!=248){send(400,"{}");return;}
    uint8_t bytes[124]={};
    for(unsigned i=0;i<248;++i){
      char c=body[i];int n=c>='0'&&c<='9'?c-'0':c>='a'&&c<='f'?c-'a'+10:-1;
      if(n<0){send(400,"{}");return;}
      if(i%2==0)bytes[i/2]=uint8_t(n<<4);else bytes[i/2]|=uint8_t(n);
    }
    const ShoulderReceiptView receipt{bytes,sizeof(bytes)};
    bool ok=start?s->begin(receipt,clock_.now_us()):s->receipt(receipt,clock_.now_us());
    send(ok?200:409,ok?"{\"accepted\":true,\"movement_performed_by_handler\":false}":"{\"accepted\":false}");
  }
  void missing(){send(409,"{\"error\":\"NO_AUTHORIZED_FAULT_SESSION\"}");}
  void send(int status,const char* raw){web_.sendHeader("Cache-Control","no-store");web_.send(status,"application/json",raw);}
  Access& access_;Clock& clock_;Web& web_;bool registered_=false;char response_[1024]={};
};
}
