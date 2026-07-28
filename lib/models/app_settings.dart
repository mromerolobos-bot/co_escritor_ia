class AppSettings {
  final String activeProvider; // 'gemini' | 'deepseek'
  final String geminiApiKey;
  final String deepseekApiKey;
  final List<String> triggerKeywords;
  final int silenceTimeoutSeconds;
  final String googleDriveFolderId;
  final String googleDocId;
  final bool hapticFeedbackEnabled;

  AppSettings({
    this.activeProvider = 'gemini',
    this.geminiApiKey = '',
    this.deepseekApiKey = '',
    List<String>? triggerKeywords,
    this.silenceTimeoutSeconds = 18,
    this.googleDriveFolderId = '1EI89xlscO7HdCZkQGwTEtZpVRR5SgbrF',
    this.googleDocId = '',
    this.hapticFeedbackEnabled = true,
  }) : triggerKeywords = triggerKeywords ?? [
          'turno de la ia',
          'opina',
          'debatamos',
          'qué piensas',
          'segui',
          'tu turno',
          'ayúdame',
          'ayudame',
        ];

  AppSettings copyWith({
    String? activeProvider,
    String? geminiApiKey,
    String? deepseekApiKey,
    List<String>? triggerKeywords,
    int? silenceTimeoutSeconds,
    String? googleDriveFolderId,
    String? googleDocId,
    bool? hapticFeedbackEnabled,
  }) {
    return AppSettings(
      activeProvider: activeProvider ?? this.activeProvider,
      geminiApiKey: geminiApiKey ?? this.geminiApiKey,
      deepseekApiKey: deepseekApiKey ?? this.deepseekApiKey,
      triggerKeywords: triggerKeywords ?? this.triggerKeywords,
      silenceTimeoutSeconds: silenceTimeoutSeconds ?? this.silenceTimeoutSeconds,
      googleDriveFolderId: googleDriveFolderId ?? this.googleDriveFolderId,
      googleDocId: googleDocId ?? this.googleDocId,
      hapticFeedbackEnabled: hapticFeedbackEnabled ?? this.hapticFeedbackEnabled,
    );
  }
}
