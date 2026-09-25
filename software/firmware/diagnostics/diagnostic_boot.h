// Diagnostic-only entry points. Included after reference declarations, replacing
// setup/loop; no legacy routes, mission playback, servo writes or serial commands.
// Not deployment approval: partition compatibility and recovery remain required.
#pragma once
bool rocellDiagnosticBootReady=false;

void setup() {
  Serial.begin(115200);
  InfoPrint=0;
  // Never format an existing filesystem because of a partition/mount mismatch.
  if(!LittleFS.begin(false))return;
  File config=LittleFS.open("/wifiConfig.json","r");
  if(!config || config.size()==0 || config.size()>1024){if(config)config.close();return;}
  JsonDocument document;
  const auto error=deserializeJson(document,config);config.close();
  if(error || !document["sta_ssid"].is<const char*>() ||
      !document["sta_password"].is<const char*>())return;
  const char* ssid=document["sta_ssid"];
  const char* password=document["sta_password"];
  if(!ssid || !password || strlen(ssid)==0 || strlen(ssid)>32 ||
      strlen(password)<8 || strlen(password)>63)return;
  // Reuse stored STA credentials only; no AP/default-password or config fallback.
  WiFi.persistent(false);
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid,password);
  const uint32_t started=millis();
  while(WiFi.status()!=WL_CONNECTED && static_cast<uint32_t>(millis()-started)<15000)delay(10);
  if(WiFi.status()!=WL_CONNECTED)return;
  // Configure transport without invoking reference initialization/check/motion.
  Serial1.begin(1000000,SERIAL_8N1,S_RXD,S_TXD);
  st.pSerial=&Serial1;
  registerDiagnosticRoutes();
  server.begin();
  rocellDiagnosticBootReady=true;
}

void loop() {
  if(rocellDiagnosticBootReady) {
#ifdef ROCELL_CONFIGURED_DIAGNOSTIC_OWNER
    rocellConfiguredRuntime.poll();
    // A slow read-only HTTP client must not hold up finite bus acquisition.
    if(!rocellConfiguredRuntime.exclusive_work())server.handleClient();
#else
    server.handleClient();
    if(rocellDiagnosticOwned)pollReceivedDiagnostic();
#endif
  }
  delay(1);
}
