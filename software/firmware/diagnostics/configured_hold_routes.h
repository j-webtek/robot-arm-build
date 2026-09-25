// Separate hold-only HTTP surface. No legacy command, reset, or baseline route.
#pragma once
bool rocellHoldChallengeAttempted=false;
bool rocellHoldConfigured=false;
char rocellHoldChallenge[512]={};
char rocellHoldPolicy[2048]={};
// Keep large response buffers off the ESP32 loop task stack. WebServer is
// serviced only by the single owner, never during active hold acquisition.
char rocellHoldResponse[4608]={};

bool rocellPrepareHoldChallenge(){
#ifdef ROCELL_POSE_OBSERVATION
  if(rocellPoseReserved)return false;
#endif
#ifdef ROCELL_RECOVERY_DIAGNOSTIC_OWNER
  if(rocellRecoveryReserved)return false;
#endif
  if(rocellHoldChallengeAttempted)return rocellHoldChallenge[0]!=0;
  rocellHoldChallengeAttempted=true;rocellDiagnosticOwned=true;
  File policy=LittleFS.open("/rocell-hold.json","r");
  if(!policy||policy.size()==0||policy.size()>=sizeof(rocellHoldPolicy)){
    policy.close();return false;
  }
  const size_t length=policy.size();
  const size_t count=policy.read(reinterpret_cast<uint8_t*>(rocellHoldPolicy),length);
  policy.close();
  if(count!=length)return false;
  rocellHoldPolicy[count]=0; // Pair handoff reparses this retained configuration.
  File key_file=LittleFS.open("/rocell-hold.key","r");
  rocell_diag::DiagnosticKeyMaterial material;
  if(!material.load(key_file)){key_file.close();return false;}
  key_file.close();
  uint8_t key[32]={},boot[16]={},nonce[32]={};
  if(!material.copy_to(key)){material.clear();return false;}
  material.clear();
  auto nibble=[](char c)->uint8_t{return c>='a'?c-'a'+10:c-'0';};
  for(size_t i=0;i<16;++i)boot[i]=(nibble(rocellDiagnosticInstance[2*i])<<4)|nibble(rocellDiagnosticInstance[2*i+1]);
  esp_fill_random(nonce,sizeof(nonce));
  const uint64_t issued=rocellConfiguredClock.now_us(),expires=issued+10000000;
  const bool ready=rocellConfiguredRuntime.initialize_config(st,rocellConfiguredClock,rocellHoldCrypto,
      key,boot,nonce,issued,expires,rocellHoldPolicy,length,rocellHoldHealthy,nullptr);
  volatile uint8_t* wipe=key;for(size_t i=0;i<sizeof(key);++i)wipe[i]=0;
  if(!ready)return false;
  char nonce_hex[65]={};const char* digits="0123456789abcdef";
  for(size_t i=0;i<32;++i){nonce_hex[2*i]=digits[nonce[i]>>4];nonce_hex[2*i+1]=digits[nonce[i]&15];}
  const int n=snprintf(rocellHoldChallenge,sizeof(rocellHoldChallenge),
      "{\"schema\":\"rocell.start_challenge.v1\",\"boot_id\":\"%s\",\"nonce\":\"%s\","
      "\"issued_us\":%llu,\"expires_us\":%llu}",rocellDiagnosticInstance,nonce_hex,
      (unsigned long long)issued,(unsigned long long)expires);
  if(n<0||size_t(n)>=sizeof(rocellHoldChallenge)){
    rocellHoldChallenge[0]=0;rocellConfiguredRuntime.export_failed();return false;
  }
  rocellHoldConfigured=true;return true;
}

void registerDiagnosticRoutes(){
  snprintf(rocellDiagnosticInstance,sizeof(rocellDiagnosticInstance),"%08lx%08lx%08lx%08lx",
      (unsigned long)esp_random(),(unsigned long)esp_random(),
      (unsigned long)esp_random(),(unsigned long)esp_random());
  server.on("/rocell/diagnostics/challenge",HTTP_GET,[](){
    server.sendHeader("Cache-Control","no-store");
    if(!rocellPrepareHoldChallenge()){
      server.send(503,"application/json","{\"error\":\"HOLD_NOT_CONFIGURED\"}");return;
    }
    // Repeated reads never renew the lease, reload policy, or rearm.
    server.send(200,"application/json",rocellHoldChallenge);
  });
  server.on("/rocell/diagnostics/status",HTTP_GET,[](){
    server.sendHeader("Cache-Control","no-store");
    bool serialized=false;
    if(rocellHoldConfigured)serialized=rocellConfiguredRuntime.status_json(rocellHoldResponse,sizeof(rocellHoldResponse));
    else {
      const int n=snprintf(rocellHoldResponse,sizeof(rocellHoldResponse),
        "{\"schema\":\"rocell.hold_transport.v1\",\"instance_id\":\"%s\",\"state\":\"%s\","
        "\"reason\":\"NOT_CONFIGURED\",\"records\":0,\"record_bytes\":4096,"
        "\"storage_fault\":false,\"durable_export_verified\":false}",
        rocellDiagnosticInstance,rocellHoldChallengeAttempted?"FAULT":"IDLE");
      serialized=n>0&&size_t(n)<sizeof(rocellHoldResponse);
    }
    if(!serialized){rocellConfiguredRuntime.export_failed();server.send(500,"application/json","{\"error\":\"SERIALIZATION_FAILED\"}");return;}
    server.send(200,"application/json",rocellHoldResponse);
  });
  server.on("/rocell/diagnostics/record",HTTP_GET,[](){
    server.sendHeader("Cache-Control","no-store");
    const String query=server.arg("index");
    unsigned index=0;
    if(query.length()==0||query.length()>2){server.send(400,"application/json","{\"error\":\"INVALID_INDEX\"}");return;}
    for(unsigned i=0;i<query.length();++i){
      if(query[i]<'0'||query[i]>'9'){server.send(400,"application/json","{\"error\":\"INVALID_INDEX\"}");return;}
      index=index*10+unsigned(query[i]-'0');
    }
    if(index>=12||!rocellConfiguredRuntime.get(index)){server.send(404,"application/json","{\"error\":\"RECORD_NOT_FOUND\"}");return;}
    if(!rocellConfiguredRuntime.record_json(index,rocellHoldResponse,sizeof(rocellHoldResponse))){
      rocellConfiguredRuntime.export_failed();server.send(500,"application/json","{\"error\":\"SERIALIZATION_FAILED\"}");return;
    }
    server.send(200,"application/json",rocellHoldResponse);
  });
}
