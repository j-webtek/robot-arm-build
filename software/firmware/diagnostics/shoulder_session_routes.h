// Uninstalled transport adapter. Access returns only an already-authorized,
// exclusively owned session. No prepare/start/reset/movement endpoint exists.
// Call web handlers and owner.advance serially on the same control task.
#pragma once
#include "shoulder_preload_session.h"
#include "shoulder_export_receipt.h"
#include <cstdio>
namespace rocell_diag {
template<class Access,class Clock,class Web> class ShoulderSessionRoutes {
 public:
  ShoulderSessionRoutes(Access& access,Clock& clock,Web& web):access_(access),clock_(clock),web_(web){}
  void register_routes(){
    if(registered_)return;registered_=true;
    web_.on("/rocell/shoulder-session/status",HTTP_GET,[this](){
      if(web_.args()!=0){error(400,"NO_PARAMETERS_ALLOWED");return;}
      auto* session=access_();if(!session){error(409,"NO_AUTHORIZED_SESSION");return;}
      const auto phase=session->phase();
      const char* state=phase==ShoulderPreloadPhase::Waiting?"WAITING_EXPORT":
        phase==ShoulderPreloadPhase::Complete?"COMPLETE":phase==ShoulderPreloadPhase::Fault?"FAULT":"RUNNING";
      // Identities are validated at session construction; JSON serialization
      // additionally escapes them rather than embedding caller-supplied text.
      JsonDocument doc;doc["schema"]="rocell.shoulder_session_status.v1";
      doc["boot_id"]=session->boot_id();doc["command_id"]=session->command_id();
      doc["state"]=state;doc["reason"]=session->reason();doc["sequence"]=session->sequence();
      doc["preload_writes"]=session->writes();doc["record_available"]=session->record()!=nullptr;
      doc["enable_delivery"]=session->enable_delivery()==ShoulderEnableDelivery::NotAttempted?
        "NOT_ATTEMPTED":"SENT_UNACKNOWLEDGED";
      doc["whole_arm_ready"]=false;doc["lift_authorized"]=false;
      if(!hold_json_finish(doc,response_,sizeof(response_))){error(500,"SERIALIZATION_FAILED");return;}
      send(200,response_);
    });
    web_.on("/rocell/shoulder-session/record",HTTP_GET,[this](){
      if(web_.args()!=0){error(400,"NO_PARAMETERS_ALLOWED");return;}
      auto* session=access_();if(!session){error(409,"NO_AUTHORIZED_SESSION");return;}
      if(!session->record()){error(404,"NO_PENDING_RECORD");return;}
      send(200,session->record());
    });
    web_.on("/rocell/shoulder-session/receipt",HTTP_POST,[this](){
      if(web_.args()!=1||web_.argName(0)!="plain"){error(400,"EXACT_RECEIPT_BODY_REQUIRED");return;}
      auto* session=access_();if(!session){error(409,"NO_AUTHORIZED_SESSION");return;}
      if(session->phase()!=ShoulderPreloadPhase::Waiting){error(409,"NOT_WAITING_EXPORT");return;}
      const auto body=web_.arg("plain");if(body.length()!=248){error(400,"INVALID_RECEIPT_LENGTH");return;}
      uint8_t bytes[124];
      for(unsigned i=0;i<248;++i){
        const char c=body[i];const int n=c>='0'&&c<='9'?c-'0':c>='a'&&c<='f'?c-'a'+10:-1;
        if(n<0){error(400,"INVALID_RECEIPT_ENCODING");return;}
        if(i%2==0)bytes[i/2]=uint8_t(n<<4);else bytes[i/2]|=uint8_t(n);
      }
      if(!session->receipt(ShoulderReceiptView{bytes,sizeof(bytes)},clock_.now_us())){
        error(409,"RECEIPT_REJECTED");return;
      }
      send(200,"{\"status\":\"EXPORT_RECEIPT_ACCEPTED\",\"movement_performed_by_handler\":false}");
    });
  }
 private:
  void send(int status,const char* bytes){web_.sendHeader("Cache-Control","no-store");web_.send(status,"application/json",bytes);}
  void error(int status,const char* reason){snprintf(response_,sizeof(response_),"{\"error\":\"%s\"}",reason);send(status,response_);}
  Access& access_;Clock& clock_;Web& web_;bool registered_=false;char response_[1024]={};
};
}
