cmake_minimum_required(VERSION 3.25)
project(rocell_windows_camera_metadata VERSION 0.1.0 LANGUAGES CXX)
if(NOT WIN32 OR NOT MSVC)
  message(FATAL_ERROR "Metadata helper requires MSVC and the Windows SDK")
endif()
set(NATIVE_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/..")
add_executable(rocell_windows_camera_metadata
  "${NATIVE_ROOT}/camera_worker.cpp"
  "${NATIVE_ROOT}/identity_metadata.cpp"
  "${NATIVE_ROOT}/admission_protocol.cpp"
  "${NATIVE_ROOT}/admission_entry.cpp")
target_compile_features(rocell_windows_camera_metadata PRIVATE cxx_std_17)
target_compile_definitions(rocell_windows_camera_metadata PRIVATE
  ROCELL_METADATA_ONLY UNICODE _UNICODE NOMINMAX WIN32_LEAN_AND_MEAN)
target_compile_options(rocell_windows_camera_metadata PRIVATE /W4 /WX /permissive- /utf-8 /guard:cf)
target_link_options(rocell_windows_camera_metadata PRIVATE /DYNAMICBASE /NXCOMPAT /guard:cf)
target_link_libraries(rocell_windows_camera_metadata PRIVATE
  mfplat mf mfreadwrite mfuuid ole32 strmiids setupapi cfgmgr32 bcrypt)

# FakeApi tests invoke no Windows metadata API, camera source or serial device.
add_executable(rocell_identity_metadata_tests
  "${NATIVE_ROOT}/identity_metadata_tests.cpp" "${NATIVE_ROOT}/identity_metadata.cpp")
target_compile_features(rocell_identity_metadata_tests PRIVATE cxx_std_17)
target_compile_definitions(rocell_identity_metadata_tests PRIVATE UNICODE _UNICODE NOMINMAX WIN32_LEAN_AND_MEAN)
target_compile_options(rocell_identity_metadata_tests PRIVATE /W4 /WX /permissive- /utf-8 /guard:cf)
target_link_options(rocell_identity_metadata_tests PRIVATE /DYNAMICBASE /NXCOMPAT /guard:cf)
target_link_libraries(rocell_identity_metadata_tests PRIVATE setupapi cfgmgr32)

enable_testing()
add_test(NAME metadata_contract_inert COMMAND rocell_windows_camera_metadata --self-test)
add_test(NAME identity_metadata_fake_api COMMAND rocell_identity_metadata_tests)
set_tests_properties(metadata_contract_inert identity_metadata_fake_api PROPERTIES TIMEOUT 10)
get_filename_component(ROCELL_TEST_PYTHON "${CMAKE_CURRENT_SOURCE_DIR}/../../../../.venv/Scripts/python.exe" ABSOLUTE)
if(NOT EXISTS "${ROCELL_TEST_PYTHON}")
  message(FATAL_ERROR "Existing workspace Python is required for metadata wire/denial tests")
endif()
add_test(NAME identity_metadata_wire_contract
  COMMAND "${ROCELL_TEST_PYTHON}" "${NATIVE_ROOT}/identity_metadata_wire_test.py" "$<TARGET_FILE:rocell_identity_metadata_tests>")
add_test(NAME metadata_active_commands_denied
  COMMAND "${ROCELL_TEST_PYTHON}" "${CMAKE_CURRENT_SOURCE_DIR}/denied_commands_test.py" "$<TARGET_FILE:rocell_windows_camera_metadata>")
set_tests_properties(identity_metadata_wire_contract metadata_active_commands_denied PROPERTIES TIMEOUT 20)
