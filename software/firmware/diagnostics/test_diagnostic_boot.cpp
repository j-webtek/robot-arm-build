// Execute the actual boot header with inert dependencies. No servo write API is
// supplied: introducing a direct write or legacy boot call fails compilation.
#include <ArduinoJson.h>
#include <cassert>
#include <cstring>
#include <cstdlib>
#include <cstdint>
int scenario=0,InfoPrint=1;
unsigned ticks=0;
unsigned millis(){return ticks;}
void delay(unsigned value){ticks+=value;}
struct UART {int begins=0;void begin(int,int=0,int=0,int=0){++begins;}} Serial,Serial1;
struct {UART* pSerial=nullptr;} st;
constexpr int SERIAL_8N1=0,S_RXD=18,S_TXD=19,WIFI_STA=1,WL_CONNECTED=3;
struct File {
  const char* data="{\"sta_ssid\":\"test-network\",\"sta_password\":\"test-only-secret\"}";
  size_t cursor=0;
  explicit operator bool() const{return scenario!=2;}
  size_t size(){return scenario==3?1025:strlen(data);}
  void close(){}
  int read(){return data[cursor]?data[cursor++]:-1;}
  size_t readBytes(char* buffer,size_t count){size_t n=0;while(n<count && data[cursor])buffer[n++]=data[cursor++];return n;}
};
struct FS {
  int opens=0;
  bool begin(bool format){assert(!format);return scenario!=1;}
  File open(const char* path,const char* mode){
    assert(strcmp(path,"/wifiConfig.json")==0 && strcmp(mode,"r")==0);++opens;
    File file;if(scenario==4)file.data="invalid";
    if(scenario==5)file.data="{\"sta_ssid\":\"test\",\"sta_password\":\"short\"}";
    return file;
  }
} LittleFS;
struct Wifi {
  int starts=0;
  void persistent(bool enabled){assert(!enabled);}
  void mode(int mode){assert(mode==WIFI_STA);}
  void begin(const char* ssid,const char* password){assert(ssid && password);++starts;}
  int status(){return scenario==6?0:WL_CONNECTED;}
} WiFi;
struct Server {int starts=0,handled=0;void begin(){++starts;}void handleClient(){++handled;}} server;
int registered=0,polled=0;
bool rocellDiagnosticOwned=false;
void registerDiagnosticRoutes(){++registered;}
void pollReceivedDiagnostic(){++polled;}
#ifdef ROCELL_CONFIGURED_DIAGNOSTIC_OWNER
struct Runtime {
  bool busy=false;void poll(){++polled;}bool exclusive_work(){return busy;}
} rocellConfiguredRuntime;
#endif
#ifdef ROCELL_RECOVERY_DIAGNOSTIC_OWNER
enum {HTTP_GET=0,HTTP_POST=1};
#include "configured_held_pair_routes.h"
Runtime rocellPairRuntime,rocellRecoveryRuntime;
#include "diagnostic_recovery_boot.h"
#else
#include "diagnostic_boot.h"
#endif
int main(int argc,char** argv){
  assert(argc==2);scenario=atoi(argv[1]);setup();
  assert(Serial.begins==1 && InfoPrint==0);
  if(scenario==0){
    assert(rocellDiagnosticBootReady && Serial1.begins==1 && st.pSerial==&Serial1);
    assert(server.starts==1 && registered==1 && WiFi.starts==1);
#ifdef ROCELL_RECOVERY_DIAGNOSTIC_OWNER
    loop();assert(server.handled==1&&polled==3);
    for(auto* runtime:{&rocellConfiguredRuntime,&rocellPairRuntime,&rocellRecoveryRuntime}){
      const int before=server.handled;runtime->busy=true;loop();assert(server.handled==before);
      runtime->busy=false;loop();assert(server.handled==before+1);
    }
#elif defined(ROCELL_CONFIGURED_DIAGNOSTIC_OWNER)
    loop();assert(server.handled==1 && polled==1);
    rocellConfiguredRuntime.busy=true;loop();assert(server.handled==1 && polled==2);
    rocellConfiguredRuntime.busy=false;loop();assert(server.handled==2 && polled==3);
#else
    loop();assert(server.handled==1 && polled==0);
    rocellDiagnosticOwned=true;loop();assert(server.handled==2 && polled==1);
#endif
  }else{
    assert(!rocellDiagnosticBootReady && Serial1.begins==0 && registered==0 && server.starts==0);
    loop();assert(server.handled==0 && polled==0);
    if(scenario==6)assert(ticks>=15000 && ticks<=15001 && WiFi.starts==1);
    else assert(WiFi.starts==0);
  }
}
