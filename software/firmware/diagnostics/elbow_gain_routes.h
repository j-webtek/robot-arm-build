// One explicit read-only acquisition per boot. GET returns retained bytes only.
#pragma once
#include "elbow_gain_json.h"
namespace rocell_diag {
template<class Bus,class Clock,class Web>
class ElbowGainRoutes {
 public:
  ElbowGainRoutes(Bus& bus,Clock& clock,Web& web,const char* boot,
      bool (*inactive)(void*),void* context=nullptr)
      :bus_(bus),clock_(clock),web_(web),boot_(boot),inactive_(inactive),context_(context){}
  void register_routes(){
    if(registered_)return;
    registered_=true;
    web_.on("/rocell/elbow-gain/capture",HTTP_POST,[this](){
      if(web_.args()!=0){send(400,"{\"error\":\"NO_PARAMETERS_ALLOWED\"}");return;}
      if(used_){send(409,"{\"error\":\"CAPTURE_ALREADY_USED\"}");return;}
      if(!inactive_||!inactive_(context_)){send(409,"{\"error\":\"BUS_NOT_INACTIVE\"}");return;}
      used_=true;
      snapshot_.acquire(bus_,clock_,inactive_,context_);
      retained_=elbow_gain_json(snapshot_,boot_,"elbow-gain-1",response_,sizeof(response_));
      if(!retained_){send(500,"{\"error\":\"SERIALIZATION_FAILED\"}");return;}
      send(200,response_); // Completeness is evidence, not inferred from HTTP 200.
    });
    web_.on("/rocell/elbow-gain/result",HTTP_GET,[this](){
      if(web_.args()!=0){send(400,"{\"error\":\"NO_PARAMETERS_ALLOWED\"}");return;}
      if(!retained_){send(404,"{\"error\":\"NO_CAPTURE\"}");return;}
      send(200,response_);
    });
  }
 private:
  void send(int code,const char* body){web_.sendHeader("Cache-Control","no-store");web_.send(code,"application/json",body);}
  Bus& bus_;Clock& clock_;Web& web_;const char* boot_;
  bool (*inactive_)(void*);void* context_;
  ElbowGainSnapshot snapshot_;char response_[4096]={};
  bool registered_=false,used_=false,retained_=false;
};
}
