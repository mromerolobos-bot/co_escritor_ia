import 'dart:async';
import 'package:connectivity_plus/connectivity_plus.dart';

enum NetworkStatus { online, weak, offline }

class ConnectivityService {
  final Connectivity _connectivity = Connectivity();
  StreamSubscription<List<ConnectivityResult>>? _subscription;

  NetworkStatus _currentStatus = NetworkStatus.offline;
  Function(NetworkStatus status)? onStatusChanged;

  NetworkStatus get currentStatus => _currentStatus;
  bool get isConnected => _currentStatus != NetworkStatus.offline;

  void initialize() {
    _subscription = _connectivity.onConnectivityChanged.listen((results) {
      _updateStatus(results);
    });

    _connectivity.checkConnectivity().then((results) {
      _updateStatus(results);
    });
  }

  void _updateStatus(List<ConnectivityResult> results) {
    if (results.contains(ConnectivityResult.mobile) ||
        results.contains(ConnectivityResult.wifi) ||
        results.contains(ConnectivityResult.ethernet)) {
      _currentStatus = NetworkStatus.online;
    } else {
      _currentStatus = NetworkStatus.offline;
    }
    onStatusChanged?.call(_currentStatus);
  }

  void dispose() {
    _subscription?.cancel();
  }
}
