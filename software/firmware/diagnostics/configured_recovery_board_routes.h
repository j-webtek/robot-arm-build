// Include after ordinary hold and pair route declarations. All preparation runs
// on the single owner. No filesystem writes, reset, servo setting write or motion.
#pragma once
#include "configured_recovery_routes.h"
#include "supported_recovery_board_policy.h"
#include <memory>
#include <new>
#if defined(ROCELL_OBSERVED_POSE_RECOVERY) && !defined(ROCELL_SIX_COUNT_RECOVERY)
#error Observed-pose recovery requires the reviewed six-count recovery runtime
#endif
struct RocellPrepareRecovery {
  struct Scratch {rocell_diag::ControllerHoldConfigParser parser;char bytes[2048]={};};
  bool operator()(char* out,size_t capacity){
#ifdef ROCELL_POSE_OBSERVATION
    if(rocellPoseReserved)return false;
#endif
    if(rocellRecoveryReserved||rocellHoldChallengeAttempted||rocellHoldConfigured||
       rocellPairRuntime.phase()!=rocell_diag::PairNetworkPhase::New||!rocellHoldHealthy(nullptr))return false;
    // Reserve before filesystem/allocations. A failed prepare is not rearmed.
    rocellRecoveryReserved=true;rocellDiagnosticOwned=true;
    std::unique_ptr<Scratch> scratch(new(std::nothrow) Scratch());
    if(!scratch)return false;
    File settings=LittleFS.open("/rocell-hold.json","r");
    if(!settings||settings.size()==0||settings.size()>=sizeof(scratch->bytes)){settings.close();return false;}
    const size_t length=settings.size();
    const size_t count=settings.read(reinterpret_cast<uint8_t*>(scratch->bytes),length);settings.close();
    if(count!=length||!scratch->parser.parse(scratch->bytes,length))return false;
    const auto& config=*scratch->parser.get();
    const bool legacy=!strcmp(config.command,"r7-supported-hold-20260918")&&
        rocell_diag::reviewed_recovery_source(config.policy);
    bool observed=false;
#ifdef ROCELL_OBSERVED_POSE_RECOVERY
    observed=!strcmp(config.command,"observed-pose-elbow-hold-v1")&&
        rocell_diag::reviewed_observed_recovery_source(config.policy);
#endif
    if(config.port!=8081||(!legacy&&!observed))return false;
    auto policy=config.policy;policy.permit_explicit_enable=false;
    File key_file=LittleFS.open("/rocell-hold.key","r");
    rocell_diag::DiagnosticKeyMaterial material;
    if(!material.load(key_file)){key_file.close();return false;}key_file.close();
    uint8_t key[32]={},boot[16]={},nonce[32]={};
    if(!material.copy_to(key)){material.clear();return false;}material.clear();
    auto nibble=[](char c)->uint8_t{return c>='a'?c-'a'+10:c-'0';};
    for(size_t i=0;i<16;++i)boot[i]=(nibble(rocellDiagnosticInstance[2*i])<<4)|nibble(rocellDiagnosticInstance[2*i+1]);
    esp_fill_random(nonce,sizeof(nonce));
    const uint64_t issued=rocellConfiguredClock.now_us(),expires=issued+10000000;
#ifdef ROCELL_SIX_COUNT_RECOVERY
    const char* command="r18-six-count-recovery";
#else
    const char* command="r15-supported-recovery";
#endif
    if(observed)command="observed-pose-six-count-recovery-v1";
    const bool ready=rocellRecoveryRuntime.initialize(st,rocellConfiguredClock,rocellHoldCrypto,
        key,boot,nonce,issued,expires,config.port,policy,command,rocellHoldHealthy,nullptr);
    volatile uint8_t* wipe=key;for(size_t i=0;i<32;++i)wipe[i]=0;
    if(!ready)return false;
    char hex[65]={};const char* digits="0123456789abcdef";
    for(size_t i=0;i<32;++i){hex[2*i]=digits[nonce[i]>>4];hex[2*i+1]=digits[nonce[i]&15];}
    const int n=snprintf(out,capacity,
      "{\"schema\":\"rocell.start_challenge.v1\",\"boot_id\":\"%s\",\"nonce\":\"%s\",\"issued_us\":%llu,\"expires_us\":%llu}",
      rocellDiagnosticInstance,hex,(unsigned long long)issued,(unsigned long long)expires);
    return n>0&&size_t(n)<capacity;
  }
};
RocellPrepareRecovery rocellPrepareRecovery;
rocell_diag::ConfiguredRecoveryRoutes<RocellRecoveryRuntime,RocellPrepareRecovery,WebServer>
    rocellRecoveryRoutes(rocellRecoveryRuntime,rocellPrepareRecovery,server);
