// Included after the existing server and read-only route definitions.
#pragma once
bool rocellChallengeAttempted=false;
char rocellChallengeJson[512]={};
char rocellPolicyBytes[4096]={};
bool rocellPrepareChallenge(){
  if(rocellChallengeAttempted)return rocellChallengeJson[0]!=0;
  rocellChallengeAttempted=true;rocellDiagnosticOwned=true;
  File policy=LittleFS.open("/rocell-diagnostics.json","r");
  if(!policy || policy.size()==0 || policy.size()>sizeof(rocellPolicyBytes)){
    policy.close();rocellConfiguredRuntime.configuration_failed();return false;
  }
  const size_t length=policy.size();
  const size_t count=policy.read(reinterpret_cast<uint8_t*>(rocellPolicyBytes),length);policy.close();
  File key_file=LittleFS.open("/rocell-diagnostics.key","r");
  rocell_diag::DiagnosticKeyMaterial material;
  if(count!=length || !material.load(key_file)){
    key_file.close();rocellConfiguredRuntime.configuration_failed();return false;
  }
  uint8_t boot[16]={},nonce[32]={};
  auto nibble=[](char c)->uint8_t{return c>='a'?c-'a'+10:c-'0';};
  for(size_t i=0;i<16;++i)boot[i]=(nibble(rocellDiagnosticInstance[2*i])<<4)|nibble(rocellDiagnosticInstance[2*i+1]);
  esp_fill_random(nonce,sizeof(nonce));
  const bool ready=rocellConfiguredRuntime.initialize(st,rocellConfiguredClock,rocellPolicyBytes,length,
      "roarm-m3-example20260115-elbow-v1",material,boot,nonce,rocellConfiguredFault,nullptr);
  material.clear();
  if(!ready)return false;
  char nonce_hex[65]={};static const char digits[]="0123456789abcdef";
  for(size_t i=0;i<32;++i){nonce_hex[2*i]=digits[nonce[i]>>4];nonce_hex[2*i+1]=digits[nonce[i]&15];}
  const int n=snprintf(rocellChallengeJson,sizeof(rocellChallengeJson),
      "{\"schema\":\"rocell.start_challenge.v1\",\"boot_id\":\"%s\",\"nonce\":\"%s\","
      "\"issued_us\":%llu,\"expires_us\":%llu}",rocellDiagnosticInstance,nonce_hex,
      (unsigned long long)rocellConfiguredRuntime.issued_us(),(unsigned long long)rocellConfiguredRuntime.expires_us());
  if(n<0 || static_cast<size_t>(n)>=sizeof(rocellChallengeJson)){
    rocellChallengeJson[0]=0;rocellConfiguredRuntime.export_failed();return false;
  }
  return true;
}
void registerConfiguredChallengeRoute(){
  server.on("/rocell/diagnostics/challenge",HTTP_GET,[](){
    server.sendHeader("Cache-Control","no-store");
    if(!rocellPrepareChallenge()){
      server.send(503,"application/json","{\"error\":\"DIAGNOSTICS_NOT_CONFIGURED\"}");return;
    }
    // Repeat reads return the same challenge, never renew its lease or owner.
    server.send(200,"application/json",rocellChallengeJson);
  });
}
