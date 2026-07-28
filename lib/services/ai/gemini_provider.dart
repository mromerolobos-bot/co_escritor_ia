import 'dart:convert';
import 'package:http/http.dart' as http;
import '../../models/story_block.dart';
import 'ai_provider.dart';

class GeminiProvider implements AIProvider {
  @override
  String get name => 'gemini';

  @override
  Future<AIResponse> generateCoWriterResponse({
    required String apiKey,
    required List<StoryBlock> history,
  }) async {
    final stopwatch = Stopwatch()..start();

    if (apiKey.trim().isEmpty) {
      return AIResponse(
        text: 'Error: API Key de Gemini no configurada en Ajustes.',
        providerName: name,
        responseTimeMs: 0,
      );
    }

    final url = Uri.parse(
        'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=$apiKey');

    // Construcción del contexto del borrador
    final formattedHistory = history.map((block) {
      final role = block.sender == 'user' ? 'user' : 'model';
      return {
        'role': role,
        'parts': [
          {'text': block.content}
        ]
      };
    }).toList();

    // Payload con safety_settings en BLOCK_NONE para evitar censura en ficción adulta
    final bodyJson = {
      'contents': formattedHistory,
      'systemInstruction': {
        'parts': [
          {'text': kSystemPrompt}
        ]
      },
      'safetySettings': [
        {
          'category': 'HARM_CATEGORY_HARASSMENT',
          'threshold': 'BLOCK_NONE'
        },
        {
          'category': 'HARM_CATEGORY_HATE_SPEECH',
          'threshold': 'BLOCK_NONE'
        },
        {
          'category': 'HARM_CATEGORY_SEXUALLY_EXPLICIT',
          'threshold': 'BLOCK_NONE'
        },
        {
          'category': 'HARM_CATEGORY_DANGEROUS_CONTENT',
          'threshold': 'BLOCK_NONE'
        }
      ],
      'generationConfig': {
        'temperature': 0.7,
        'maxOutputTokens': 800,
      }
    };

    try {
      final response = await http.post(
        url,
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode(bodyJson),
      );

      stopwatch.stop();

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final candidates = data['candidates'] as List?;
        if (candidates != null && candidates.isNotEmpty) {
          final parts = candidates[0]['content']['parts'] as List?;
          if (parts != null && parts.isNotEmpty) {
            final text = parts[0]['text'] as String;
            return AIResponse(
              text: text.trim(),
              providerName: name,
              responseTimeMs: stopwatch.elapsedMilliseconds,
            );
          }
        }
        return AIResponse(
          text: 'La IA devolvió una respuesta vacía.',
          providerName: name,
          responseTimeMs: stopwatch.elapsedMilliseconds,
        );
      } else {
        return AIResponse(
          text: 'Error de Gemini (${response.statusCode}): ${response.body}',
          providerName: name,
          responseTimeMs: stopwatch.elapsedMilliseconds,
        );
      }
    } catch (e) {
      stopwatch.stop();
      return AIResponse(
        text: 'Error de conexión con Gemini: $e',
        providerName: name,
        responseTimeMs: stopwatch.elapsedMilliseconds,
      );
    }
  }
}
