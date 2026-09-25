// Host-test serial emulator only. Never include this directory in firmware builds.
#pragma once
#include <stddef.h>
#include <stdint.h>
#include <deque>
#include <vector>
unsigned long millis();
class HardwareSerial {
 public:
  int read();
  size_t write(const unsigned char* data,size_t count);
  bool automatic=true,drop_write_ack=false,bad_ack=false;
  bool follow_target=false,bad_read_checksum=false,wrong_read_id=false;
  unsigned writes=0;
  unsigned position[7]={2048,2390,1727,2723,2041,2042,2051};
  unsigned goal[7]={},torque[7]={};
  std::vector<std::vector<uint8_t>> packets;
 private:
  void respond();
  std::vector<uint8_t> pending;
  std::deque<uint8_t> incoming;
};
