import 'database_service.dart';
import 'google_docs_service.dart';

class SyncQueueService {
  final DatabaseService _db = DatabaseService.instance;
  final GoogleDocsService _docsService = GoogleDocsService();
  bool _isSyncing = false;

  bool get isSyncing => _isSyncing;

  Future<void> processSyncQueue(String googleDocId) async {
    if (_isSyncing || googleDocId.trim().isEmpty) return;
    _isSyncing = true;

    try {
      final unsynced = await _db.getUnsyncedBlocks();
      if (unsynced.isNotEmpty) {
        final success = await _docsService.appendBlocksToDoc(
          docId: googleDocId,
          blocks: unsynced,
        );

        if (success) {
          final ids = unsynced.map((b) => b.id!).toList();
          await _db.markBlocksAsSynced(ids);
        }
      }
    } finally {
      _isSyncing = false;
    }
  }
}
