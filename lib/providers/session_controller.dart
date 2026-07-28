import 'package:flutter/foundation.dart';
import '../models/app_settings.dart';
import '../models/story_block.dart';
import '../services/ai/ai_provider.dart';
import '../services/ai/deepseek_provider.dart';
import '../services/ai/gemini_provider.dart';
import '../services/connectivity_service.dart';
import '../services/database_service.dart';
import '../services/google_docs_service.dart';
import '../services/settings_service.dart';
import '../services/stt_service.dart';
import '../services/sync_queue_service.dart';
import '../services/tts_service.dart';

enum DrivingSessionState { idle, listening, thinking, speaking, offlineQueued }

class SessionController extends ChangeNotifier {
  final DatabaseService _db = DatabaseService.instance;
  final SettingsService _settingsService = SettingsService();
  final STTService _sttService = STTService();
  final TTSService _ttsService = TTSService();
  final ConnectivityService _connectivityService = ConnectivityService();
  final SyncQueueService _syncQueueService = SyncQueueService();
  final GoogleDocsService _googleDocsService = GoogleDocsService();

  DrivingSessionState _sessionState = DrivingSessionState.idle;
  AppSettings _settings = AppSettings();
  NetworkStatus _networkStatus = NetworkStatus.offline;

  List<StoryBlock> _history = [];
  String _liveTranscription = '';
  String _lastAiResponse = '';
  bool _isSessionActive = false;

  DrivingSessionState get sessionState => _sessionState;
  AppSettings get settings => _settings;
  NetworkStatus get networkStatus => _networkStatus;
  List<StoryBlock> get history => _history;
  String get liveTranscription => _liveTranscription;
  String get lastAiResponse => _lastAiResponse;
  bool get isSessionActive => _isSessionActive;

  final GeminiProvider _geminiProvider = GeminiProvider();
  final DeepSeekProvider _deepSeekProvider = DeepSeekProvider();

  Future<void> initSession() async {
    _settings = await _settingsService.loadSettings();
    _history = await _db.getAllBlocks();

    if (_history.isNotEmpty) {
      final lastAi = _history.lastWhere(
        (b) => b.sender == 'ai',
        orElse: () => StoryBlock(sender: 'ai', content: '', timestamp: ''),
      );
      _lastAiResponse = lastAi.content;
    }

    await _ttsService.initialize();
    _sttService.configure(
      silenceTimeoutSeconds: _settings.silenceTimeoutSeconds,
      triggerKeywords: _settings.triggerKeywords,
    );

    _sttService.onPartialResult = (partialText) {
      _liveTranscription = partialText;
      notifyListeners();
    };

    _sttService.onSpeechChunkCompleted = _handleSpeechChunkCompleted;

    _connectivityService.onStatusChanged = (status) {
      _networkStatus = status;
      notifyListeners();
      if (_connectivityService.isConnected && _settings.googleDocId.isNotEmpty) {
        _syncQueueService.processSyncQueue(_settings.googleDocId);
      }
    };
    _connectivityService.initialize();
  }

  Future<void> updateSettings(AppSettings newSettings) async {
    _settings = newSettings;
    await _settingsService.saveSettings(newSettings);
    _sttService.configure(
      silenceTimeoutSeconds: _settings.silenceTimeoutSeconds,
      triggerKeywords: _settings.triggerKeywords,
    );
    notifyListeners();
  }

  Future<void> toggleSession() async {
    if (_isSessionActive) {
      await stopSession();
    } else {
      await startSession();
    }
  }

  Future<void> startSession() async {
    _isSessionActive = true;
    _sessionState = DrivingSessionState.listening;
    notifyListeners();
    await _sttService.startListening();
  }

  Future<void> stopSession() async {
    _isSessionActive = false;
    _sessionState = DrivingSessionState.idle;
    await _sttService.stopListening();
    await _ttsService.stop();
    notifyListeners();

    // Intentar sincronizar cola pendiente al detener
    if (_connectivityService.isConnected && _settings.googleDocId.isNotEmpty) {
      await _syncQueueService.processSyncQueue(_settings.googleDocId);
    }
  }

  Future<void> triggerManualDebate() async {
    if (_history.isEmpty) return;
    await _requestAiDebate();
  }

  Future<void> triggerManualSync() async {
    if (_settings.googleDocId.isNotEmpty) {
      await _syncQueueService.processSyncQueue(_settings.googleDocId);
    }
  }

  void _handleSpeechChunkCompleted(STTResultEvent event) async {
    if (event.text.trim().isNotEmpty) {
      // Guardar inmediatamente en SQLite
      final userBlock = StoryBlock(
        sender: 'user',
        content: event.text,
        timestamp: DateTime.now().toIso8601String(),
      );

      final savedBlock = await _db.insertBlock(userBlock);
      _history.add(savedBlock);
      _liveTranscription = event.text;
      notifyListeners();
    }

    if (event.triggerType == STTTriggerType.statusQuery) {
      await _ttsService.confirmSavedQuietly();
      return;
    }

    if (event.triggerType == STTTriggerType.keyword || event.triggerType == STTTriggerType.silence) {
      await _requestAiDebate();
    }
  }

  Future<void> _requestAiDebate() async {
    if (_history.isEmpty) return;

    if (!_connectivityService.isConnected) {
      _sessionState = DrivingSessionState.offlineQueued;
      notifyListeners();
      await _ttsService.speak('Guardado en memoria local. Esperando señal para debatir.');
      return;
    }

    _sessionState = DrivingSessionState.thinking;
    notifyListeners();

    AIProvider activeProvider =
        _settings.activeProvider == 'deepseek' ? _deepSeekProvider : _geminiProvider;
    String apiKey = _settings.activeProvider == 'deepseek'
        ? _settings.deepseekApiKey
        : _settings.geminiApiKey;

    final response = await activeProvider.generateCoWriterResponse(
      apiKey: apiKey,
      history: _history.take(15).toList(), // Enviar los últimos 15 bloques
    );

    _lastAiResponse = response.text;

    // Guardar respuesta de IA en SQLite
    final aiBlock = StoryBlock(
      sender: 'ai',
      content: response.text,
      timestamp: DateTime.now().toIso8601String(),
      providerUsed: response.providerName,
      responseTimeMs: response.responseTimeMs,
    );

    final savedAiBlock = await _db.insertBlock(aiBlock);
    _history.add(savedAiBlock);

    _sessionState = DrivingSessionState.speaking;
    notifyListeners();

    // Leer por TTS
    await _ttsService.speak(response.text);

    _sessionState = DrivingSessionState.listening;
    notifyListeners();
  }

  Future<bool> signInGoogle() async {
    final account = await _googleDocsService.signIn();
    notifyListeners();
    return account != null;
  }
}
