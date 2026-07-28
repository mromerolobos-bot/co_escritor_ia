import 'dart:io';
import 'package:path/path.dart';
import 'package:path_provider/path_provider.dart';
import 'package:sqflite/sqflite.dart';
import '../models/story_block.dart';

class DatabaseService {
  static final DatabaseService instance = DatabaseService._init();
  static Database? _database;

  DatabaseService._init();

  Future<Database> get database async {
    if (_database != null) return _database!;
    _database = await _initDB('story_journal.db');
    return _database!;
  }

  Future<Database> _initDB(String filePath) async {
    final dbPath = await getDatabasesPath();
    final path = join(dbPath, filePath);

    return await openDatabase(
      path,
      version: 1,
      onCreate: _createDB,
    );
  }

  Future<void> _createDB(Database db, int version) async {
    await db.execute('''
      CREATE TABLE story_blocks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender TEXT NOT NULL,
        content TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        is_synced INTEGER NOT NULL DEFAULT 0,
        provider_used TEXT,
        response_time_ms INTEGER
      )
    ''');
  }

  /// Inserción ultra-rápida en SQLite + respaldo inmediato en archivo .txt
  Future<StoryBlock> insertBlock(StoryBlock block) async {
    final db = await instance.database;
    final id = await db.insert('story_blocks', block.toMap());
    final newBlock = StoryBlock(
      id: id,
      sender: block.sender,
      content: block.content,
      timestamp: block.timestamp,
      isSyncedGoogleDoc: block.isSyncedGoogleDoc,
      providerUsed: block.providerUsed,
      responseTimeMs: block.responseTimeMs,
    );

    // Respaldo redundante paralelo en archivo .txt
    await _writeRedundantTxtBackup(newBlock);

    return newBlock;
  }

  Future<List<StoryBlock>> getAllBlocks() async {
    final db = await instance.database;
    final result = await db.query('story_blocks', orderBy: 'id ASC');
    return result.map((json) => StoryBlock.fromMap(json)).toList();
  }

  Future<List<StoryBlock>> getUnsyncedBlocks() async {
    final db = await instance.database;
    final result = await db.query(
      'story_blocks',
      where: 'is_synced = ?',
      whereArgs: [0],
      orderBy: 'id ASC',
    );
    return result.map((json) => StoryBlock.fromMap(json)).toList();
  }

  Future<void> markBlocksAsSynced(List<int> ids) async {
    if (ids.isEmpty) return;
    final db = await instance.database;
    final idList = ids.join(',');
    await db.rawUpdate(
      'UPDATE story_blocks SET is_synced = 1 WHERE id IN ($idList)',
    );
  }

  /// Escribe la frase directamente en un diario diario .txt local como segunda capa de seguridad
  Future<void> _writeRedundantTxtBackup(StoryBlock block) async {
    try {
      final dir = await getApplicationDocumentsDirectory();
      final dateStr = DateTime.now().toIso8601String().substring(0, 10);
      final file = File('${dir.path}/story_backup_$dateStr.txt');
      final logLine = '[${block.timestamp}] [${block.sender.toUpperCase()}]: ${block.content}\n\n';
      await file.writeAsString(logLine, mode: FileMode.append);
    } catch (e) {
      // Ignorar silencio si no hay permisos de sistema operativo
    }
  }
}
