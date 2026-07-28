import 'package:google_sign_in/google_sign_in.dart';
import 'package:googleapis/docs/v1.dart' as docs;
import 'package:http/http.dart' as http;
import '../models/story_block.dart';

class GoogleAuthClient extends http.BaseClient {
  final Map<String, String> _headers;
  final http.Client _client = http.Client();

  GoogleAuthClient(this._headers);

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) {
    request.headers.addAll(_headers);
    return _client.send(request);
  }
}

class GoogleDocsService {
  final GoogleSignIn _googleSignIn = GoogleSignIn(
    scopes: [
      docs.DocsApi.documentsScope,
      docs.DocsApi.driveFileScope,
    ],
  );

  GoogleSignInAccount? _currentUser;

  GoogleSignInAccount? get currentUser => _currentUser;
  bool get isSignedIn => _currentUser != null;

  Future<GoogleSignInAccount?> signIn() async {
    try {
      _currentUser = await _googleSignIn.signIn();
      return _currentUser;
    } catch (e) {
      return null;
    }
  }

  Future<void> signOut() async {
    await _googleSignIn.signOut();
    _currentUser = null;
  }

  Future<bool> appendBlocksToDoc({
    required String docId,
    required List<StoryBlock> blocks,
  }) async {
    if (blocks.isEmpty || docId.trim().isEmpty) return false;

    try {
      _currentUser ??= await _googleSignIn.signInSilently();
      if (_currentUser == null) return false;

      final authHeaders = await _currentUser!.authHeaders;
      final httpClient = GoogleAuthClient(authHeaders);
      final docsApi = docs.DocsApi(httpClient);

      // Obtener el documento actual para saber el índice final
      final doc = await docsApi.documents.get(docId);
      final endIndex = doc.body?.content?.last.endIndex ?? 1;
      final targetIndex = endIndex > 1 ? endIndex - 1 : 1;

      final buffer = StringBuffer();
      for (final block in blocks) {
        final senderTag = block.sender == 'user' ? 'NARRADOR' : 'EDITOR IA';
        buffer.writeln('[$senderTag - ${block.timestamp}]');
        buffer.writeln(block.content);
        buffer.writeln('----------------------------------------\n');
      }

      final requests = [
        docs.Request(
          insertText: docs.InsertTextRequest(
            text: buffer.toString(),
            location: docs.Location(index: targetIndex),
          ),
        ),
      ];

      final batchRequest = docs.BatchUpdateDocumentRequest(requests: requests);
      await docsApi.documents.batchUpdate(batchRequest, docId);
      httpClient.close();
      return true;
    } catch (e) {
      return false;
    }
  }
}
