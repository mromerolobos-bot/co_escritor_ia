import 'dart:convert';
import 'package:http/http.dart' as http;
import '../../models/story_block.dart';
import 'ai_provider.dart';

class DeepSeekProvider implements AIProvider {
  @override
  String get name => 'deepseek';

  @override
  Future<AIResponse> generateCoWriterResponse({
    required String apiKey,
    required List<StoryBlock> history,
  }) async {
    final stopwatch = Stopwatch()..start();

    if (apiKey.trim().isEmpty) {
      return AIResponse(
        text: 'Error: API Key de DeepSeek no configurada en Ajustes.',
        providerName: name,
        responseTimeMs: 0,
      );
    }

    final url = Uri.parse('https://api.deepseek.com/chat/completions');

    final messages = <Map<String, String>>[
      {'role': 'system', 'content': kSystemPrompt},
    ];

    for (final block in history) {
      final role = block.sender == 'user' ? 'user' : 'assistant';
      messages.add({'role': role, 'content': block.content});
    }

    final bodyJson = {
      'model': 'deepseek-chat',
      'messages': messages,
      'temperature': 0.7,
      'max_tokens': 800,
    };

    try {
      final response = await http.post(
        url,
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer $apiKey',
        },
        body: jsonEncode(bodyJson),
      );

      stopwatch.stop();

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final choices = data['choices'] as List?;
        if (choices != null && choices.isNotEmpty) {
          final content = choices[0]['message']['content'] as String?;
          if (content != null) {
            return AIResponse(
              text: content.trim(),
              providerName: name,
              responseTimeMs: stopwatch.elapsedMilliseconds,
            );
          }
        }
        return AIResponse(
          text: 'DeepSeek devolvió una respuesta vacía.',
          providerName: name,
          responseTimeMs: stopwatch.elapsedMilliseconds,
        );
      } else {
        return AIResponse(
          text: 'Error de DeepSeek (${response.statusCode}): ${response.body}',
          providerName: name,
          responseTimeMs: stopwatch.elapsedMilliseconds,
        );
      }
    } catch (e) {
      stopwatch.stop();
      return AIResponse(
        text: 'Error de conexión con DeepSeek: $e',
        providerName: name,
        responseTimeMs: stopwatch.elapsedMilliseconds,
      );
    }
  }
}
