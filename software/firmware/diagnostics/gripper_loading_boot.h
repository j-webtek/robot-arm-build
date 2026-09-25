// Single-purpose loading boot. No startup servo command, mission, or generic
// UART/HTTP command parser. Wi-Fi is only used for read-only identity.
#pragma once
#include "gripper_loading_board.h"
rocell_diag::GripperLoadingBoard rocellGripperLoader;
bool rocellGripperBootReady=false;
void setup(){
  Serial.begin(115200);InfoPrint=0;
  if(!LittleFS.begin(false))return;
  File config=LittleFS.open("/wifiConfig.json","r");
  if(!config||config.size()==0||config.size()>1024){if(config)config.close();return;}
  JsonDocument document;const auto error=deserializeJson(document,config);config.close();
  if(error||!document["sta_ssid"].is<const char*>()||
     !document["sta_password"].is<const char*>())return;
  const char* ssid=document["sta_ssid"],*password=document["sta_password"];
  if(!ssid||!password||strlen(ssid)==0||strlen(ssid)>32||strlen(password)<8||strlen(password)>63)return;
  WiFi.persistent(false);WiFi.mode(WIFI_STA);WiFi.begin(ssid,password);
  const uint32_t started=millis();
  while(WiFi.status()!=WL_CONNECTED&&uint32_t(millis()-started)<15000)delay(10);
  if(WiFi.status()!=WL_CONNECTED)return;
  Serial1.begin(1000000,SERIAL_8N1,S_RXD,S_TXD);st.pSerial=&Serial1;
  snprintf(rocellDiagnosticInstance,sizeof(rocellDiagnosticInstance),"%08lx%08lx%08lx%08lx",
      (unsigned long)esp_random(),(unsigned long)esp_random(),
      (unsigned long)esp_random(),(unsigned long)esp_random());
  rocellGripperLoader.begin();
  server.begin();rocellGripperBootReady=true;
}
void loop(){
  if(rocellGripperBootReady){
    rocellGripperLoader.poll();
    server.handleClient();
  }
  delay(1);
}
