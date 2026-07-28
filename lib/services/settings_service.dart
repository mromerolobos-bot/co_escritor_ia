import 'package:shared_preferences/shared_preferences.dart';
import '../models/app_settings.dart';

class SettingsService {
  static const _keyActiveProvider = 'active_provider';
  static const _keyGeminiKey = 'gemini_api_key';
  static const _keyDeepseekKey = 'deepseek_api_key';
  static const _keyKeywords = 'trigger_keywords';
  static const _keySilenceTimeout = 'silence_timeout_seconds';
  static const _keyFolderId = 'google_drive_folder_id';
  static const _keyDocId = 'google_doc_id';
  static const _keyHaptic = 'haptic_feedback_enabled';

  Future<AppSettings> loadSettings() async {
    final prefs = await SharedPreferences.getInstance();
    final activeProvider = prefs.getString(_keyActiveProvider) ?? 'gemini';
    final geminiKey = prefs.getString(_keyGeminiKey) ?? '';
    final deepseekKey = prefs.getString(_keyDeepseekKey) ?? '';
    final keywordsString = prefs.getString(_keyKeywords);
    final silenceTimeout = prefs.getInt(_keySilenceTimeout) ?? 18;
    final folderId = prefs.getString(_keyFolderId) ?? '1EI89xlscO7HdCZkQGwTEtZpVRR5SgbrF';
    final docId = prefs.getString(_keyDocId) ?? '';
    final haptic = prefs.getBool(_keyHaptic) ?? true;

    List<String>? keywords;
    if (keywordsString != null && keywordsString.trim().isNotEmpty) {
      keywords = keywordsString
          .split(',')
          .map((e) => e.trim().toLowerCase())
          .where((e) => e.isNotEmpty)
          .toList();
    }

    return AppSettings(
      activeProvider: activeProvider,
      geminiApiKey: geminiKey,
      deepseekApiKey: deepseekKey,
      triggerKeywords: keywords,
      silenceTimeoutSeconds: silenceTimeout,
      googleDriveFolderId: folderId,
      googleDocId: docId,
      hapticFeedbackEnabled: haptic,
    );
  }

  Future<void> saveSettings(AppSettings settings) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_keyActiveProvider, settings.activeProvider);
    await prefs.setString(_keyGeminiKey, settings.geminiApiKey);
    await prefs.setString(_keyDeepseekKey, settings.deepseekApiKey);
    await prefs.setString(_keyKeywords, settings.triggerKeywords.join(', '));
    await prefs.setInt(_keySilenceTimeout, settings.silenceTimeoutSeconds);
    await prefs.setString(_keyFolderId, settings.googleDriveFolderId);
    await prefs.setString(_keyDocId, settings.googleDocId);
    await prefs.setBool(_keyHaptic, settings.hapticFeedbackEnabled);
  }
}
