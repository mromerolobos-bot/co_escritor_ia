import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/session_controller.dart';
import '../widgets/big_action_buttons.dart';
import '../widgets/live_transcription_box.dart';
import '../widgets/signal_status_banner.dart';
import 'settings_screen.dart';

class DrivingModeScreen extends StatelessWidget {
  const DrivingModeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Consumer<SessionController>(
      builder: (context, controller, child) {
        return Scaffold(
          backgroundColor: const Color(0xFF0F0F1A),
          appBar: AppBar(
            backgroundColor: const Color(0xFF151525),
            elevation: 0,
            title: const Text(
              'CO-ESCRITOR IA (MODO MANEJO)',
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.bold,
                letterSpacing: 1,
                color: Colors.white,
              ),
            ),
            centerTitle: true,
            actions: [
              IconButton(
                icon: const Icon(Icons.settings, color: Colors.white),
                onPressed: () {
                  Navigator.push(
                    context,
                    MaterialPageRoute(builder: (context) => const SettingsScreen()),
                  );
                },
              ),
            ],
          ),
          body: SafeArea(
            child: Column(
              children: [
                // 📶 Bandera de Calidad de Señal
                SignalStatusBanner(status: controller.networkStatus),
                const SizedBox(height: 12),
                // 💬 Cajas de Transcripción y Respuesta IA
                Expanded(
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 16),
                    child: LiveTranscriptionBox(
                      userText: controller.liveTranscription,
                      aiText: controller.lastAiResponse,
                    ),
                  ),
                ),
                const SizedBox(height: 16),
                // 🔘 Botones Gigantes para Conducción
                Padding(
                  padding: const EdgeInsets.all(16.0),
                  child: BigActionButtons(
                    isSessionActive: controller.isSessionActive,
                    sessionState: controller.sessionState,
                    onToggleSession: () => controller.toggleSession(),
                    onDebatePressed: () => controller.triggerManualDebate(),
                    onSyncPressed: () => controller.triggerManualSync(),
                    onSettingsPressed: () {
                      Navigator.push(
                        context,
                        MaterialPageRoute(builder: (context) => const SettingsScreen()),
                      );
                    },
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}
