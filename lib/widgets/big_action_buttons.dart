import 'package:flutter/material.dart';
import '../providers/session_controller.dart';

class BigActionButtons extends StatelessWidget {
  final bool isSessionActive;
  final DrivingSessionState sessionState;
  final VoidCallback onToggleSession;
  final VoidCallback onDebatePressed;
  final VoidCallback onSyncPressed;
  final VoidCallback onSettingsPressed;

  const BigActionButtons({
    super.key,
    required this.isSessionActive,
    required this.sessionState,
    required this.onToggleSession,
    required this.onDebatePressed,
    required this.onSyncPressed,
    required this.onSettingsPressed,
  });

  @override
  Widget build(BuildContext context) {
    String stateLabel = 'INICIAR DICTADO';
    Color mainButtonColor = Colors.green.shade700;
    IconData mainIcon = Icons.mic;

    if (isSessionActive) {
      switch (sessionState) {
        case DrivingSessionState.thinking:
          stateLabel = 'IA PENSANDO...';
          mainButtonColor = Colors.purple.shade700;
          mainIcon = Icons.hourglass_top;
          break;
        case DrivingSessionState.speaking:
          stateLabel = 'IA HABLANDO...';
          mainButtonColor = Colors.blue.shade700;
          mainIcon = Icons.volume_up;
          break;
        case DrivingSessionState.offlineQueued:
          stateLabel = 'GUARDADO LOCAL (EN COLA)';
          mainButtonColor = Colors.amber.shade800;
          mainIcon = Icons.wifi_off;
          break;
        case DrivingSessionState.listening:
        default:
          stateLabel = 'ESCUCHANDO (DETENER)';
          mainButtonColor = Colors.red.shade700;
          mainIcon = Icons.stop;
          break;
      }
    }

    return Column(
      children: [
        // 💡 Botón Gigante de Pedir Opinión / Debatir
        SizedBox(
          width: double.infinity,
          height: 64,
          child: ElevatedButton.icon(
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFF6C5CE7),
              foregroundColor: Colors.white,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(16),
              ),
              elevation: 4,
            ),
            onPressed: onDebatePressed,
            icon: const Icon(Icons.lightbulb_sharp, size: 28),
            label: const Text(
              'DEBATIR / PEDIR OPINIÓN DE IA',
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, letterSpacing: 0.5),
            ),
          ),
        ),
        const SizedBox(height: 12),
        // 🎙️ Botón Principal de Iniciar/Detener Dictado (Gran tamaño)
        SizedBox(
          width: double.infinity,
          height: 76,
          child: ElevatedButton.icon(
            style: ElevatedButton.styleFrom(
              backgroundColor: mainButtonColor,
              foregroundColor: Colors.white,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(20),
              ),
              elevation: 6,
            ),
            onPressed: onToggleSession,
            icon: Icon(mainIcon, size: 36),
            label: Text(
              stateLabel,
              style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, letterSpacing: 1),
            ),
          ),
        ),
        const SizedBox(height: 12),
        // Acciones Secundarias: Sincronizar y Ajustes
        Row(
          children: [
            Expanded(
              child: OutlinedButton.icon(
                style: OutlinedButton.styleFrom(
                  foregroundColor: Colors.white,
                  side: const BorderSide(color: Colors.white38, width: 1.5),
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
                onPressed: onSyncPressed,
                icon: const Icon(Icons.sync, size: 20),
                label: const Text('SINCRONIZAR'),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: OutlinedButton.icon(
                style: OutlinedButton.styleFrom(
                  foregroundColor: Colors.white,
                  side: const BorderSide(color: Colors.white38, width: 1.5),
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
                onPressed: onSettingsPressed,
                icon: const Icon(Icons.settings, size: 20),
                label: const Text('AJUSTES'),
              ),
            ),
          ],
        )
      ],
    );
  }
}
