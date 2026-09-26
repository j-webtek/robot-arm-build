"""Deterministically stage the minimal offline r97 production-runtime candidate.

Filesystem-only: this script does not compile, install, start, open a port, or
move hardware.  The staged sketch deliberately excludes the vendor Wi-Fi,
HTTP, ESP-NOW, filesystem, mission, torque, and generic-command surfaces.
"""

from __future__ import annotations

import hashlib
from pathlib import Path


TARGET = "configured-diagnostic-candidate-r97"


SKETCH = r'''#include <Arduino.h>
#include <SCServo.h>
#include <esp_ota_ops.h>
#include <esp_partition.h>
#include <math.h>
#include "production_runtime_v1.h"

ProductionRuntimeV1 runtime;

void setup() {
  runtime.begin();
}

void loop() {
  runtime.poll();
}
'''.encode("ascii")


RUNTIME = r'''#pragma once

// r97 is intentionally a narrow serial runtime.  Startup initializes only the
// host UART and the servo bus UART; it performs zero servo writes and zero
// feedback reads.  No persisted settings or credentials are read or changed.

class ProductionRuntimeV1 {
 public:
  static constexpr size_t kMaximumWireBytes = 512;
  static constexpr size_t kMaximumPayloadBytes = kMaximumWireBytes - 1;
  static constexpr uint32_t kHostBaud = 115200;
  static constexpr uint32_t kServoBaud = 1000000;
  static constexpr int kServoRx = 18;
  static constexpr int kServoTx = 19;

  void begin() {
    Serial.begin(kHostBaud);
    Serial1.begin(kServoBaud, SERIAL_8N1, kServoRx, kServoTx);
    servo_.pSerial = &Serial1;
    emitAttestation();
  }

  void poll() {
    while (Serial.available() > 0) {
      const int incoming = Serial.read();
      if (incoming < 0) return;
      if (terminal_locked_) continue;
      if (incoming == '\r') {
        lockTerminal("NONCANONICAL_CARRIAGE_RETURN");
        continue;
      }
      if (incoming == '\n') {
        line_[line_length_] = '\0';
        dispatchLine();
        line_length_ = 0;
        continue;
      }
      if (line_length_ >= kMaximumPayloadBytes) {
        lockTerminal("OVERLONG_LINE");
        continue;
      }
      line_[line_length_++] = static_cast<char>(incoming);
    }
  }

 private:
  static constexpr double kPi = 3.14159265358979323846;
  static constexpr int16_t kMiddle = 2047;
  static constexpr double kStepsPerRadian = 4096.0 / (2.0 * kPi);
  static constexpr uint8_t kServoIds[7] = {11, 12, 13, 14, 15, 16, 17};

  SMS_STS servo_;
  char line_[kMaximumPayloadBytes + 1]{};
  size_t line_length_ = 0;
  bool terminal_locked_ = false;
  uint32_t accepted_ordinal_ = 0;

  static bool hasWhitespace(const char* value) {
    for (const unsigned char* p = reinterpret_cast<const unsigned char*>(value);
         *p; ++p) {
      if (*p == ' ' || *p == '\t' || *p == '\r' || *p == '\n') return true;
    }
    return false;
  }

  void dispatchLine() {
    if (line_length_ == 0) {
      lockTerminal("EMPTY_LINE");
      return;
    }
    if (strcmp(line_, "{\"T\":105}") == 0) {
      emitFeedback();
      return;
    }
    if (strncmp(line_, "{\"T\":102,", 9) == 0) {
      acceptJointCommand();
      return;
    }
    lockTerminal("UNSUPPORTED_OR_MALFORMED_COMMAND");
  }

  void acceptJointCommand() {
    if (hasWhitespace(line_)) {
      lockTerminal("NONCANONICAL_WHITESPACE");
      return;
    }
    double base, shoulder, elbow, wrist, roll, hand;
    unsigned long speed, acceleration;
    int consumed = -1;
    const int fields = sscanf(
        line_,
        "{\"T\":102,\"base\":%lf,\"shoulder\":%lf,\"elbow\":%lf,"
        "\"wrist\":%lf,\"roll\":%lf,\"hand\":%lf,\"spd\":%lu,"
        "\"acc\":%lu}%n",
        &base, &shoulder, &elbow, &wrist, &roll, &hand,
        &speed, &acceleration, &consumed);
    if (fields != 8 || consumed != static_cast<int>(line_length_) ||
        !isfinite(base) || !isfinite(shoulder) || !isfinite(elbow) ||
        !isfinite(wrist) || !isfinite(roll) || !isfinite(hand) ||
        speed < 1 || speed > 65535 || acceleration < 1 || acceleration > 255) {
      lockTerminal("INVALID_T102");
      return;
    }

    int16_t goals[7];
    goals[0] = static_cast<int16_t>(lround(-constrain(base, -kPi, kPi) *
                                          kStepsPerRadian) + kMiddle);
    const int16_t shoulder_delta = static_cast<int16_t>(lround(
        constrain(shoulder, -kPi / 2.0, kPi / 2.0) * kStepsPerRadian));
    goals[1] = kMiddle + shoulder_delta;
    goals[2] = kMiddle - shoulder_delta;
    goals[3] = constrain(static_cast<int>(lround(elbow * kStepsPerRadian) + 1024),
                         1024, 3071);
    goals[4] = static_cast<int16_t>(lround(
        constrain(wrist, -kPi / 2.0, kPi / 2.0) * kStepsPerRadian) + kMiddle);
    goals[5] = static_cast<int16_t>(lround(-constrain(roll, -kPi, kPi) *
                                          kStepsPerRadian) + kMiddle);
    goals[6] = constrain(static_cast<int>(lround(hand * kStepsPerRadian)),
                         700, 3396);
    uint16_t speeds[7];
    uint8_t accelerations[7];
    for (size_t i = 0; i < 7; ++i) {
      speeds[i] = static_cast<uint16_t>(speed);
      accelerations[i] = static_cast<uint8_t>(acceleration);
    }

    // Exactly one servo-bus group write.  No firmware retry or replay exists.
    servo_.SyncWritePosEx(const_cast<uint8_t*>(kServoIds), 7, goals, speeds,
                          accelerations);
    ++accepted_ordinal_;
    Serial.printf("{\"T\":1021,\"status\":\"ACCEPTED_ONCE\","
                  "\"ordinal\":%lu}\n",
                  static_cast<unsigned long>(accepted_ordinal_));
  }

  bool readServo(uint8_t id, int16_t* position) {
    if (servo_.FeedBack(id) == -1) return false;
    *position = servo_.ReadPos(-1);
    return true;
  }

  void emitFeedback() {
    int16_t position[7];
    for (size_t i = 0; i < 7; ++i) {
      if (!readServo(kServoIds[i], &position[i])) {
        lockTerminal("FEEDBACK_READ_FAILED");
        return;
      }
    }
    const double base = -(position[0] * 2.0 * kPi / 4096.0) + kPi;
    const double shoulder = (position[1] * 2.0 * kPi / 4096.0) - kPi;
    const double elbow = (position[3] * 2.0 * kPi / 4096.0) - kPi / 2.0;
    const double wrist = (position[4] * 2.0 * kPi / 4096.0) - kPi;
    const double roll = -(position[5] * 2.0 * kPi / 4096.0) + kPi;
    const double hand = position[6] * 2.0 * kPi / 4096.0;
    Serial.printf("{\"T\":1051,\"b\":%.9g,\"s\":%.9g,\"e\":%.9g,"
                  "\"t\":%.9g,\"r\":%.9g,\"g\":%.9g}\n",
                  base, shoulder, elbow, wrist, roll, hand);
  }

  void lockTerminal(const char* reason) {
    terminal_locked_ = true;
    Serial.printf("{\"T\":9002,\"state\":\"TERMINAL_LOCKED\","
                  "\"reason\":\"%s\"}\n", reason);
  }

  void emitAttestation() {
    uint8_t digest[32]{};
    char hex[65]{};
    const esp_partition_t* running = esp_ota_get_running_partition();
    const esp_err_t result = running ? esp_partition_get_sha256(running, digest)
                                     : ESP_ERR_NOT_FOUND;
    if (result == ESP_OK) {
      static const char alphabet[] = "0123456789abcdef";
      for (size_t i = 0; i < 32; ++i) {
        hex[i * 2] = alphabet[digest[i] >> 4];
        hex[i * 2 + 1] = alphabet[digest[i] & 0x0f];
      }
    } else {
      strcpy(hex, "UNAVAILABLE");
    }
    Serial.printf("{\"T\":9000,\"runtime\":\"rocell.production_runtime.v1\","
                  "\"candidate\":\"r97\",\"state\":\"SAFE_IDLE\","
                  "\"startup_motion_commands\":0,\"automatic_retry\":false,"
                  "\"supported_commands\":[102,105],\"app_sha256\":\"%s\","
                  "\"protocol_source_sha256\":\"@PROTOCOL_SOURCE_SHA256@\","
                  "\"joint_mapping_source_sha256\":\"@JOINT_MAPPING_SOURCE_SHA256@\","
                  "\"configuration_epoch_sha256\":null}\n", hex);
  }
};
'''.encode("ascii")


def sources(root: Path) -> dict[str, bytes]:
    root = Path(root).resolve()
    protocol_sha = hashlib.sha256(
        (root / "src/rocell/arm/all_joint_command.py").read_bytes()).hexdigest()
    mapping_sha = hashlib.sha256(
        (root / "src/rocell/arm/joint_mapping.py").read_bytes()).hexdigest()
    runtime = RUNTIME.replace(b"@PROTOCOL_SOURCE_SHA256@", protocol_sha.encode())
    runtime = runtime.replace(b"@JOINT_MAPPING_SOURCE_SHA256@", mapping_sha.encode())
    files = {
        "RoArm-M3_example.ino": SKETCH,
        "production_runtime_v1.h": runtime,
    }
    forbidden = (
        b"WiFi", b"WebServer", b"esp_now", b"LittleFS", b"Preferences",
        b"nvs_", b"serialCtrl", b"webCtrlServer", b"mission", b"Torque",
        b"servo_.WritePosEx(",
    )
    combined = b"\n".join(files.values())
    for token in forbidden:
        if token in combined:
            raise ValueError(f"Forbidden r97 runtime token: {token!r}")
    required = (
        b"startup_motion_commands", b"SyncWritePosEx", b"{\\\"T\\\":105}",
        b"TERMINAL_LOCKED", b"esp_partition_get_sha256",
    )
    for token in required:
        if token not in combined:
            raise ValueError(f"Missing r97 runtime token: {token!r}")
    if combined.count(b"SyncWritePosEx") != 1:
        raise ValueError("r97 must contain exactly one group-write call site")
    return files


def stage(root: Path) -> dict:
    root = Path(root).resolve()
    files = sources(root)
    destination = root / ".firmware-tools" / TARGET / "RoArm-M3_example"
    existing = ({path.name: path.read_bytes() for path in destination.iterdir()
                 if path.is_file()} if destination.exists() else {})
    if existing and existing != files:
        raise ValueError("Existing r97 stage differs; refusing to overwrite")
    destination.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        path = destination / name
        if not path.exists():
            with path.open("xb") as stream:
                stream.write(data)
        if path.read_bytes() != data:
            raise ValueError("Staged r97 source readback differs")
    return {
        "status": "STAGED_OFFLINE_NOT_COMPILED_NOT_INSTALLED",
        "target": TARGET,
        "source_hashes": {
            name: hashlib.sha256(data).hexdigest()
            for name, data in sorted(files.items())
        },
        "startup_motion_commands": 0,
        "hardware_access": False,
        "firmware_uploaded": False,
        "motion_authorized": False,
    }


if __name__ == "__main__":
    import json

    print(json.dumps(stage(Path(__file__).resolve().parents[1]), indent=2))
