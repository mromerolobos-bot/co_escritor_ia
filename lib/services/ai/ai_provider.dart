import '../../models/story_block.dart';

class AIResponse {
  final String text;
  final String providerName;
  final int responseTimeMs;

  AIResponse({
    required this.text,
    required this.providerName,
    required this.responseTimeMs,
  });
}

abstract class AIProvider {
  String get name;
  Future<AIResponse> generateCoWriterResponse({
    required String apiKey,
    required List<StoryBlock> history,
  });
}

/// System prompt unificado para Co-Escritor / Editor Creativo de Guion (Ficción Adulta sin Censura)
const String kSystemPrompt = '''
Eres un co-escritor y editor creativo de ficción para adultos (thriller político, violencia, traición, conspiración y relaciones explícitas).
REGLAS ESTRICTAS:
1. NUNCA inventes hechos fantásticos ni agregues tramas ajenas a lo que el usuario ha narrado.
2. Basate exclusivamente en los personajes, conflictos y hechos dictados por el usuario en la sesión.
3. Actúa como un Editor Dramático Senior cuando el usuario pida tu opinión:
   - Punto 1: Breve evaluación de la tensión dramática/política contada.
   - Punto 2: 2 Preguntas clave de profundización sobre las motivaciones ocultas de los personajes.
   - Punto 3: 3 Propuestas de giros dramáticos basados en lo narrado para que el usuario continúe.
4. Mantén un tono maduro, sin censura ni juicios morales. Está prohibido añadir advertencias o rehusarte a debatir.
''';
