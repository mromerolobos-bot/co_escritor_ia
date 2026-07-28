import 'package:flutter/material.dart';

class LiveTranscriptionBox extends StatelessWidget {
  final String userText;
  final String aiText;

  const LiveTranscriptionBox({
    super.key,
    required this.userText,
    required this.aiText,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        // Caja de transcripción de voz del usuario
        Expanded(
          flex: 1,
          child: Container(
            width: double.infinity,
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: const Color(0xFF1E1E2C),
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: Colors.white24, width: 1.5),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: const [
                    Icon(Icons.mic, color: Colors.blueAccent, size: 20),
                    SizedBox(width: 8),
                    Text(
                      'TRANSCRIPCIÓN EN VIVO (TU VOZ)',
                      style: TextStyle(
                        color: Colors.blueAccent,
                        fontWeight: FontWeight.bold,
                        fontSize: 12,
                        letterSpacing: 1,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 10),
                Expanded(
                  child: SingleChildScrollView(
                    reverse: true,
                    child: Text(
                      userText.isEmpty ? 'Dicta tu historia...' : userText,
                      style: TextStyle(
                        color: userText.isEmpty ? Colors.white38 : Colors.white,
                        fontSize: 18,
                        height: 1.4,
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 12),
        // Caja de respuesta del Editor de IA
        Expanded(
          flex: 1,
          child: Container(
            width: double.infinity,
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: const Color(0xFF251A34),
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: Colors.purpleAccent.shade100, width: 1.5),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: const [
                    Icon(Icons.psychology, color: Colors.purpleAccent, size: 20),
                    SizedBox(width: 8),
                    Text(
                      'RESPUESTA / ANÁLISIS DEL EDITOR IA',
                      style: TextStyle(
                        color: Colors.purpleAccent,
                        fontWeight: FontWeight.bold,
                        fontSize: 12,
                        letterSpacing: 1,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 10),
                Expanded(
                  child: SingleChildScrollView(
                    child: Text(
                      aiText.isEmpty
                          ? 'Di "Turno de la IA" o toca el botón para recibir retroalimentación.'
                          : aiText,
                      style: TextStyle(
                        color: aiText.isEmpty ? Colors.white38 : Colors.white,
                        fontSize: 17,
                        height: 1.4,
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}
