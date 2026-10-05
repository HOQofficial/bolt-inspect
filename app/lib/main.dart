// 볼트 체결 타격음 진단 앱 — ESP32 BLE 프로토타입 클라이언트
//
// 준비물: flutter create . 로 이 폴더에 프로젝트 뼈대를 생성한 뒤
//         android/ios 폴더가 생기면 이 lib/main.dart 로 교체하고
//         pubspec.yaml 의 flutter_blue_plus 의존성을 추가한 상태에서
//         `flutter pub get` 후 실행하세요.
//
// 펌웨어(bolt_tap_sensor.ino)가 BLE 기기 이름 "BoltTapSensor" 로 광고하고
// SERVICE_UUID / CHAR_MEASURE_UUID 로 JSON 문자열을 Notify 하는 것을 그대로 매칭합니다.

import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_blue_plus/flutter_blue_plus.dart';

const String kServiceUuid = "6e400001-b5a3-f393-e0a9-e50e24dcca9e";
const String kMeasureCharUuid = "6e400002-b5a3-f393-e0a9-e50e24dcca9e";
const String kDeviceName = "BoltTapSensor";

void main() => runApp(const BoltApp());

class BoltApp extends StatelessWidget {
  const BoltApp({super.key});
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: '볼트 체결 진단',
      theme: ThemeData(useMaterial3: true, colorSchemeSeed: Colors.blue),
      home: const BoltHomePage(),
    );
  }
}

class BoltHomePage extends StatefulWidget {
  const BoltHomePage({super.key});
  @override
  State<BoltHomePage> createState() => _BoltHomePageState();
}

class _BoltHomePageState extends State<BoltHomePage> {
  BluetoothDevice? _device;
  bool _connecting = false;
  bool _connected = false;

  String _status = "센서를 연결하세요";
  double _peakFreq = 0;
  double _centroid = 0;
  double _decay = 0;
  int _confidence = 0;
  DateTime? _lastUpdate;

  Future<void> _scanAndConnect() async {
    setState(() => _connecting = true);

    // 위치/블루투스 권한은 앱 최초 실행 시 OS가 자동으로 요청합니다.
    // (Android 12+는 BLUETOOTH_SCAN/CONNECT 권한이 AndroidManifest.xml에 필요)
    await FlutterBluePlus.startScan(timeout: const Duration(seconds: 6));

    final sub = FlutterBluePlus.scanResults.listen((results) async {
      for (final r in results) {
        if (r.device.platformName == kDeviceName) {
          await FlutterBluePlus.stopScan();
          await _connectToDevice(r.device);
          break;
        }
      }
    });

    await Future.delayed(const Duration(seconds: 6));
    await sub.cancel();
    if (mounted) setState(() => _connecting = false);
  }

  Future<void> _connectToDevice(BluetoothDevice device) async {
    try {
      await device.connect(timeout: const Duration(seconds: 10));
      final services = await device.discoverServices();

      for (final service in services) {
        if (service.uuid.str128.toLowerCase() == kServiceUuid) {
          for (final c in service.characteristics) {
            if (c.uuid.str128.toLowerCase() == kMeasureCharUuid) {
              await c.setNotifyValue(true);
              c.lastValueStream.listen(_onMeasurement);
            }
          }
        }
      }

      setState(() {
        _device = device;
        _connected = true;
        _status = "연결됨 — 볼트를 타격하세요";
      });
    } catch (e) {
      setState(() => _status = "연결 실패: $e");
    }
  }

  void _onMeasurement(List<int> value) {
    try {
      final jsonStr = utf8.decode(value);
      final data = jsonDecode(jsonStr) as Map<String, dynamic>;
      setState(() {
        _status = data["status"] as String;
        _peakFreq = (data["peak_freq"] as num).toDouble();
        _centroid = (data["centroid"] as num).toDouble();
        _decay = (data["decay"] as num? ?? 0).toDouble();
        _confidence = (data["confidence"] as num).toInt();
        _lastUpdate = DateTime.now();
      });
    } catch (_) {
      // 파싱 실패한 패킷은 무시 (통신 노이즈 등)
    }
  }

  Color get _statusColor {
    if (_status.contains("정상")) return Colors.green;
    if (_status.contains("이완") || _status.contains("과체결")) return Colors.orange;
    return Colors.blueGrey;
  }

  @override
  void dispose() {
    _device?.disconnect();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text("볼트 체결 진단")),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              _status.contains("정상")
                  ? Icons.check_circle
                  : Icons.warning_amber_rounded,
              color: _statusColor,
              size: 72,
            ),
            const SizedBox(height: 16),
            Text(_status,
                style: TextStyle(
                    fontSize: 26,
                    fontWeight: FontWeight.bold,
                    color: _statusColor)),
            const SizedBox(height: 24),
            _infoRow("공진주파수", "${_peakFreq.toStringAsFixed(1)} Hz"),
            _infoRow("스펙트럼 중심", "${_centroid.toStringAsFixed(1)} Hz"),
            _infoRow("감쇠율", _decay.toStringAsFixed(3)),
            _infoRow("신뢰도", "$_confidence %"),
            if (_lastUpdate != null)
              _infoRow("측정 시각",
                  "${_lastUpdate!.hour.toString().padLeft(2, '0')}:${_lastUpdate!.minute.toString().padLeft(2, '0')}:${_lastUpdate!.second.toString().padLeft(2, '0')}"),
            const SizedBox(height: 32),
            FilledButton.icon(
              onPressed: _connecting ? null : _scanAndConnect,
              icon: const Icon(Icons.bluetooth_searching),
              label: Text(_connecting
                  ? "검색 중..."
                  : (_connected ? "재연결" : "센서 연결")),
            ),
          ],
        ),
      ),
    );
  }

  Widget _infoRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(color: Colors.grey)),
          Text(value, style: const TextStyle(fontWeight: FontWeight.w600)),
        ],
      ),
    );
  }
}
