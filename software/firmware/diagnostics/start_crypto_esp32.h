// Uses the crypto library shipped with the pinned ESP32 core. No custom hash.
#pragma once
#include <mbedtls/md.h>
#include <cstddef>
#include <cstdint>
namespace rocell_diag {
struct Esp32StartCrypto {
  bool sha256(const uint8_t* data,size_t length,uint8_t (&out)[32]) {
    const mbedtls_md_info_t* info=mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
    return info && mbedtls_md(info,data,length,out)==0;
  }
  bool hmac_sha256(const uint8_t (&key)[32],const uint8_t* data,size_t length,uint8_t (&out)[32]) {
    const mbedtls_md_info_t* info=mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
    return info && mbedtls_md_hmac(info,key,32,data,length,out)==0;
  }
};
}
