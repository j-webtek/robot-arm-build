// Registration only: outer loop polls the sole owner after request handling.
// Caller must also gate motion/challenge ingress with DiagnosticSessionClaim.
#pragma once
#include "baseline_only_owner.h"
#include "start_plan_structure.h"
namespace rocell_diag {
template<class Server,class Owner>
void register_baseline_only_routes(Server& server,Owner& owner) {
  server.on("/rocell/diagnostics/baseline",HTTP_POST,[&server,&owner](){
    server.sendHeader("Cache-Control","no-store");
    const auto body=server.arg("plain");
    StrictPlanJson lexical;JsonDocument document;
    if(!body.length() || body.length()>512 ||
       !lexical.check(body.c_str(),body.length()) ||
       deserializeJson(document,body.c_str(),body.length(),DeserializationOption::NestingLimit(2))){
      server.send(400,"application/json","{\"error\":\"INVALID_BASELINE_REQUEST\"}");return;
    }
    const auto root=document.template as<JsonVariantConst>();
    static const char* const fields[]={"boot_id","scan_id"};
    if(!plan_fields(root,fields,2)||!root["boot_id"].is<const char*>()||
       !root["scan_id"].is<const char*>()){
      server.send(400,"application/json","{\"error\":\"INVALID_BASELINE_REQUEST\"}");return;
    }
    if(!owner.request(root["boot_id"].as<const char*>(),root["scan_id"].as<const char*>())){
      server.send(409,"application/json","{\"error\":\"BASELINE_NOT_ADMITTED\"}");return;
    }
    server.send(202,"application/json","{\"status\":\"BASELINE_QUEUED\"}");
  });
  server.on("/rocell/diagnostics/baseline",HTTP_GET,[&server,&owner](){
    server.sendHeader("Cache-Control","no-store");
    if(!owner.record()[0]){
      server.send(409,"application/json","{\"error\":\"BASELINE_NOT_AVAILABLE\"}");return;
    }
    // A faulted partial scan is valid evidence, not a successful baseline.
    server.send(200,"application/json",owner.record());
  });
}
}
