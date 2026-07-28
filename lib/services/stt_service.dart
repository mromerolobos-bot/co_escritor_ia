import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:speech_to_text/speech_recognition_result.dart';
import 'package:speech_to_text/speech_to_text.dart';

enum STTTriggerType { silence, keyword, statusQuery, normal }

class STTResultEvent {
  final String text;
  final STTTriggerType triggerType;

  STTResultEvent({required this.text, required this.triggerType});
}

class STTService {
  final SpeechToText _speech = SpeechToText();
  bool _isInitialized = false;
  bool _isListening = false;

  Timer? _silenceTimer;
  int _silenceTimeoutSeconds = 18;
  List<String> _triggerKeywords = [];

  Function(STTResultEvent event)? onSpeechChunkCompleted;
  Function(String partialText)? onPartialResult;
  VoidCallback? onErrorOrTimeout;

  bool get isListening => _isListening;

  Future<bool> initialize() async {
    if (_isInitialized) return true;
    _isInitialized = await _speech.initialize(
      onError: (val) {
        if (kDebugMode) print('STT Error: $val');
        _isListening = false;
        onErrorOrTimeout?.call();
      },
      onStatus: (status) {
        if (kDebugMode) print('STT Status: $status');
        if (status == 'done' || status == 'notListening') {
          _isListening = false;
        }
      },
    );
    return _isInitialized;
  }

  void configure({
    required int silenceTimeoutSeconds,
    required List<String> triggerKeywords,
  }) {
    _silenceTimeoutSeconds = silenceTimeoutSeconds;
    _triggerKeywords = triggerKeywords.map((e) => e.toLowerCase()).toList();
  }

  Future<void> startListening() async {
    if (!_isInitialized) {
      final initialized = await initialize();
      if (!initialized) return;
    }

    _isListening = true;
    _resetSilenceTimer();

    await _speech.listen(
      onResult: _handleSpeechResult,
      listenFor: const Duration(hours: 2), // Escucha extendida continua
      pauseFor: Duration(seconds: _silenceTimeoutSeconds),
      partialResults: true,
      localeId: 'es_CL', // Español de Chile / Neutro
      cancelOnError: false,
      listenMode: ListenMode.dictation,
    );
  }

  Future<void> stopListening() async {
    _silenceTimer?.cancel();
    _isListening = false;
    await _speech.stop();
  }

  void _handleSpeechResult(SpeechRecognitionResult result) {
    _resetSilenceTimer();
    final recognizedWords = result.recognizedWords.trim();

    onPartialResult?.call(recognizedWords);

    if (result.finalResult && recognizedWords.isNotEmpty) {
      final lowerText = recognizedWords.toLowerCase();

      // Check if user is asking for saving status ("¿se guardó?", "todo bien?")
      if (lowerText.contains('se guardó') || lowerText.contains('se guardo') || lowerText.contains('esta guardado')) {
        onSpeechChunkCompleted?.call(STTResultEvent(
          text: recognizedWords,
          triggerType: STTTriggerType.statusQuery,
        ));
        return;
      }

      // Check if any configurable keyword matches
      bool isKeywordTrigger = false;
      for (final kw in _triggerKeywords) {
        if (lowerText.contains(kw)) {
          isKeywordTrigger = true;
          break;
        }
      }

      final trigger = isKeywordTrigger ? STTTriggerType.keyword : STTTriggerType.normal;

      onSpeechChunkCompleted?.call(STTResultEvent(
        text: recognizedWords,
        triggerType: trigger,
      ));
    }
  }

  void _resetSilenceTimer() {
    _silenceTimer?.cancel();
    _silenceTimer = Timer(Duration(seconds: _silenceTimeoutSeconds), () {
      if (_isListening) {
        // Enviar evento de silencio detectado
        onSpeechChunkCompleted?.call(STTResultEvent(
          text: '',
          triggerType: STTTriggerType.silence,
        ));
      }
    });
  }
}
