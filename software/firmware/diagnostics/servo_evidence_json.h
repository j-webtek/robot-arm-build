// Bounded acquisition-pair serialization. No allocation, transport or native I/O.
#pragma once
#include "servo_evidence.h"
#include <stddef.h>
#include <stdio.h>
#include <string.h>

namespace rocell_diag {
inline bool valid_identity(const char* value) {
  if (!value || !*value) return false;
  for (size_t i=0; i<=128; ++i) {
    const char c=value[i];
    if (!c) return true;
    if (i==128 || !((c>='a' && c<='z') || (c>='A' && c<='Z') ||
        (c>='0' && c<='9') || c=='_' || c=='-' || c=='.')) return false;
  }
  return false;
}

inline bool read_json(const ReadEvidence& r, const char* boot, const char* command,
                      char* output, size_t capacity) {
  if (!output || capacity==0) return false;
  output[0]=0;
  if (!valid_identity(boot) || !valid_identity(command) || r.servo_id<1 ||
      r.servo_id>253 || !((r.address==42 && r.width==2) ||
      (r.address==56 && r.width==15)) || r.started_us>INT64_MAX ||
      r.finished_us>INT64_MAX || r.finished_us<r.started_us ||
      r.device_error < -1 || r.device_error>255) return false;
  const bool success=r.status==ReadStatus::Succeeded;
  if ((!success && r.status!=ReadStatus::Failed) ||
      (success && (r.returned_bytes!=r.width || r.device_error!=0))) return false;
  char raw[33] = "null";
  if (success) {
    const char* hex="0123456789abcdef";
    raw[0]='"';
    for (size_t i=0;i<r.width;++i) {
      raw[1+2*i]=hex[r.bytes[i]>>4];raw[2+2*i]=hex[r.bytes[i]&15];
    }
    raw[1+2*r.width]='"';raw[2+2*r.width]=0;
  }
  char error[5]="null";
  if (r.device_error>=0) snprintf(error,sizeof(error),"%d",r.device_error);
  const int n=snprintf(output,capacity,
      "{\"boot_id\":\"%s\",\"command_id\":\"%s\",\"servo_id\":%u,"
      "\"sequence\":%lu,\"read_started_us\":%llu,\"read_finished_us\":%llu,"
      "\"address\":%u,\"width\":%u,\"status\":\"%s\",\"device_error\":%s,\"raw_hex\":%s}",
      boot,command,r.servo_id,(unsigned long)r.sequence,
      (unsigned long long)r.started_us,(unsigned long long)r.finished_us,
      r.address,r.width,success?"SUCCEEDED":"FAILED",error,raw);
  if (n<0 || static_cast<size_t>(n)>=capacity) { output[0]=0;return false; }
  return true;
}

inline bool pair_json(const PairEvidence& pair,const char* boot,const char* command,
                      const char* byte_order,char* output,size_t capacity) {
  if (!output || capacity==0) return false;
  output[0]=0;
  if (!byte_order || (strcmp(byte_order,"little") && strcmp(byte_order,"big")) ||
      pair.target.address!=42 || pair.feedback.address!=56 ||
      pair.target.servo_id!=pair.feedback.servo_id) return false;
  char target[768],feedback[768];
  if (!read_json(pair.target,boot,command,target,sizeof(target)) ||
      !read_json(pair.feedback,boot,command,feedback,sizeof(feedback))) return false;
  const int n=snprintf(output,capacity,
      "{\"schema\":\"rocell.servo_acquisition_pair.v1\","
      "\"profile_id\":\"waveshare-sms-sts-reference-b8b377642b3e\","
      "\"byte_order\":\"%s\",\"target\":%s,\"feedback\":%s}",byte_order,target,feedback);
  if (n<0 || static_cast<size_t>(n)>=capacity) { output[0]=0;return false; }
  return true;
}
} // namespace rocell_diag
