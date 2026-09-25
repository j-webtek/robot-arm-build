// ESP32 system RNG adapter; construction has no side effects.
#pragma once
#include <esp_random.h>
#include <stdint.h>
#include <stddef.h>
namespace rocell_diag {
struct Esp32PairEntropy {
  bool fill(uint8_t* out,size_t length){
    if(!out||length!=32)return false;
    esp_fill_random(out,length);return true;
  }
};
}
