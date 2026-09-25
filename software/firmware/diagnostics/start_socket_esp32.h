// Pinned ESP32 core 3.0.7: bypass NetworkClient::write's internal select/retry
// loop. Use a dedicated accepted client; never mix buffered NetworkClient reads
// with these raw fd reads. The client reference must outlive this adapter.
#pragma once
#include <NetworkClient.h>
#include <lwip/sockets.h>
#include <errno.h>
namespace rocell_diag {
class Esp32StartSocket {
 public:
  explicit Esp32StartSocket(NetworkClient& client):client_(client) {}
  int receive(uint8_t* output,size_t capacity){
    if(client_.fd()<0)return -1;
    return result(recv(client_.fd(),output,capacity,MSG_DONTWAIT));
  }
  int send_once(const uint8_t* bytes,size_t length){
    if(client_.fd()<0)return -1;
    return result(send(client_.fd(),bytes,length,MSG_DONTWAIT));
  }
  void close(){client_.stop();}
 private:
  static int result(int n){return n>=0?n:(errno==EAGAIN || errno==EWOULDBLOCK?-2:-1);}
  NetworkClient& client_;
};
}
