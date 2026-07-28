class StoryBlock {
  final int? id;
  final String sender; // 'user' | 'ai'
  final String content;
  final String timestamp;
  final bool isSyncedGoogleDoc;
  final String? providerUsed; // 'gemini' | 'deepseek'
  final int? responseTimeMs;

  StoryBlock({
    this.id,
    required this.sender,
    required this.content,
    required this.timestamp,
    this.isSyncedGoogleDoc = false,
    this.providerUsed,
    this.responseTimeMs,
  });

  Map<String, dynamic> toMap() {
    return {
      if (id != null) 'id': id,
      'sender': sender,
      'content': content,
      'timestamp': timestamp,
      'is_synced': isSyncedGoogleDoc ? 1 : 0,
      'provider_used': providerUsed,
      'response_time_ms': responseTimeMs,
    };
  }

  factory StoryBlock.fromMap(Map<String, dynamic> map) {
    return StoryBlock(
      id: map['id'] as int?,
      sender: map['sender'] as String? ?? 'user',
      content: map['content'] as String? ?? '',
      timestamp: map['timestamp'] as String? ?? DateTime.now().toIso8601String(),
      isSyncedGoogleDoc: (map['is_synced'] as int? ?? 0) == 1,
      providerUsed: map['provider_used'] as String?,
      responseTimeMs: map['response_time_ms'] as int?,
    );
  }
}
