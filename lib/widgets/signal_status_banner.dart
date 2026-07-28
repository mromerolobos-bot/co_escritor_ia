import 'package:flutter/material.dart';
import '../services/connectivity_service.dart';

class SignalStatusBanner extends StatelessWidget {
  final NetworkStatus status;

  const SignalStatusBanner({super.key, required this.status});

  @override
  Widget build(BuildContext context) {
    Color backgroundColor;
    IconData iconData;
    String statusText;

    switch (status) {
      case NetworkStatus.online:
        backgroundColor = Colors.green.shade800;
        iconData = Icons.wifi_sharp;
        statusText = 'SEÑAL EXCELENTE - LA IA RESPONDERÁ AL INSTANTE';
        break;
      case NetworkStatus.weak:
        backgroundColor = Colors.amber.shade900;
        iconData = Icons.network_check;
        statusText = 'SEÑAL DÉBIL - LA IA PODRÍA TARDAR UN MOMENTO';
        break;
      case NetworkStatus.offline:
      default:
        backgroundColor = Colors.red.shade900;
        iconData = Icons.wifi_off_sharp;
        statusText = 'SIN SEÑAL (MODO OFFLINE) - DICTADO SEGURO LOCAL';
        break;
    }

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 16),
      color: backgroundColor,
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(iconData, color: Colors.white, size: 22),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              statusText,
              style: const TextStyle(
                color: Colors.white,
                fontWeight: FontWeight.bold,
                fontSize: 13,
                letterSpacing: 0.5,
              ),
              textAlign: TextAlign.center,
            ),
          ),
        ],
      ),
    );
  }
}
