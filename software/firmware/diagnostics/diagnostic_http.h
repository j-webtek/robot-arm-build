// Included after the synchronous WebServer instance. Read-only endpoints do not
// dispatch, sample, reset sessions, erase records, or acknowledge disk export.
#pragma once
#include "diagnostic_session.h"
#include "evidence_store.h"
#include "diagnostic_status_json.h"
#ifndef ROCELL_NATIVE_DIAGNOSTIC_OWNER
rocell_diag::DiagnosticSession rocellDiagnosticSession;
rocell_diag::EvidenceStore<16> rocellDiagnosticEvidence;
char rocellDiagnosticInstance[33]={};
#endif

void registerDiagnosticRoutes() {
  // Register after Wi-Fi initialization, where ESP32 hardware RNG has entropy.
  // This correlates a boot instance; it is not an authentication credential.
  if(!rocellDiagnosticInstance[0]) {
    snprintf(rocellDiagnosticInstance,sizeof(rocellDiagnosticInstance),"%08lx%08lx%08lx%08lx",
        static_cast<unsigned long>(esp_random()),static_cast<unsigned long>(esp_random()),
        static_cast<unsigned long>(esp_random()),static_cast<unsigned long>(esp_random()));
  }
  server.on("/rocell/diagnostics/status",HTTP_GET,[](){
    char body[512];
    const bool start_capable=
#ifdef ROCELL_CONFIGURED_DIAGNOSTIC_OWNER
        true;
#else
        false;
#endif
    if(!rocell_diag::diagnostic_status_json(rocellDiagnosticSession,rocellDiagnosticEvidence,
        rocellDiagnosticInstance,body,sizeof(body),start_capable)) {
      rocellDiagnosticSession.export_failed();
      server.send(500,"application/json","{\"error\":\"SERIALIZATION_FAILED\"}");return;
    }
    server.sendHeader("Cache-Control","no-store");
    server.send(200,"application/json",body);
  });
  server.on("/rocell/diagnostics/record",HTTP_GET,[](){
    const String query=server.arg("index");
    // No signed values, whitespace, coercion or unbounded integer conversion.
    if(query.length()==0 || query.length()>2) {
      server.send(400,"application/json","{\"error\":\"INVALID_INDEX\"}");return;
    }
    unsigned index=0;
    for(unsigned i=0;i<query.length();++i) {
      if(query[i]<'0' || query[i]>'9') {
        server.send(400,"application/json","{\"error\":\"INVALID_INDEX\"}");return;
      }
      index=index*10+static_cast<unsigned>(query[i]-'0');
    }
    const auto* record=rocellDiagnosticEvidence.get(index);
    if(!record){server.send(404,"application/json","{\"error\":\"RECORD_NOT_FOUND\"}");return;}
    char body[2304];
    const int n=snprintf(body,sizeof(body),
        "{\"schema\":\"rocell.diagnostic_record.v2\",\"instance_id\":\"%s\",\"index\":%u,\"kind\":\"%s\",\"record\":%s}",
        rocellDiagnosticInstance,index,record->kind,record->json);
    if(n<0 || static_cast<size_t>(n)>=sizeof(body)) {
      rocellDiagnosticSession.export_failed();
      server.send(500,"application/json","{\"error\":\"SERIALIZATION_FAILED\"}");return;
    }
    server.sendHeader("Cache-Control","no-store");
    server.send(200,"application/json",body);
  });
#ifdef ROCELL_CONFIGURED_DIAGNOSTIC_OWNER
  registerConfiguredChallengeRoute();
#endif
}
#ifdef ROCELL_CONFIGURED_DIAGNOSTIC_OWNER
#include "configured_diagnostic_routes.h"
#endif
