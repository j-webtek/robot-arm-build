// Shared read-only status encoding for legacy and authenticated session owners.
// v3 advertises the separate authenticated start capability, never authority.
#pragma once
#include <stdio.h>
#include "diagnostic_session.h"
namespace rocell_diag {
template<class Owner,class Store>
bool diagnostic_status_json(const Owner& owner,const Store& store,const char* instance,char* output,size_t capacity,bool start_capable=false) {
  if(!output || !capacity)return false;
  output[0]=0;
  if(!valid_identity(instance) || strlen(instance)!=32)return false;
  const auto state=owner.state();
  const char* name=state==SessionState::Idle?"IDLE":state==SessionState::Sampling?"SAMPLING":
      state==SessionState::Captured?"CAPTURED":"FAULT";
  const char* reason=owner.reason();
  // Reasons must be fixed diagnostic identifiers, never reflected input.
  if(!valid_identity(reason))return false;
  const int n=snprintf(output,capacity,
      "{\"schema\":\"rocell.diagnostic_transport.%s\",\"instance_id\":\"%s\",\"state\":\"%s\","
      "\"reason\":\"%s\",\"records\":%u,\"storage_fault\":%s,"
      "\"start_supported\":%s,\"durable_export_verified\":false}",
      start_capable?"v3":"v2",instance,name,reason,static_cast<unsigned>(store.size()),store.faulted()?"true":"false",
      start_capable?"true":"false");
  if(n<0 || static_cast<size_t>(n)>=capacity){output[0]=0;return false;}
  return true;
}
}
