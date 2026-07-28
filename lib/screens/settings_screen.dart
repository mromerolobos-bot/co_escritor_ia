import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../models/app_settings.dart';
import '../providers/session_controller.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  late String _activeProvider;
  late TextEditingController _geminiKeyController;
  late TextEditingController _deepseekKeyController;
  late TextEditingController _keywordsController;
  late TextEditingController _folderIdController;
  late TextEditingController _docIdController;
  late double _silenceTimeout;

  @override
  void initState() {
    super.initState();
    final settings = Provider.of<SessionController>(context, listen: false).settings;
    _activeProvider = settings.activeProvider;
    _geminiKeyController = TextEditingController(text: settings.geminiApiKey);
    _deepseekKeyController = TextEditingController(text: settings.deepseekApiKey);
    _keywordsController = TextEditingController(text: settings.triggerKeywords.join(', '));
    _folderIdController = TextEditingController(text: settings.googleDriveFolderId);
    _docIdController = TextEditingController(text: settings.googleDocId);
    _silenceTimeout = settings.silenceTimeoutSeconds.toDouble();
  }

  @override
  void dispose() {
    _geminiKeyController.dispose();
    _deepseekKeyController.dispose();
    _keywordsController.dispose();
    _folderIdController.dispose();
    _docIdController.dispose();
    super.dispose();
  }

  void _saveAll() {
    final controller = Provider.of<SessionController>(context, listen: false);

    final keywordsList = _keywordsController.text
        .split(',')
        .map((e) => e.trim().toLowerCase())
        .where((e) => e.isNotEmpty)
        .toList();

    final newSettings = AppSettings(
      activeProvider: _activeProvider,
      geminiApiKey: _geminiKeyController.text.trim(),
      deepseekApiKey: _deepseekKeyController.text.trim(),
      triggerKeywords: keywordsList,
      silenceTimeoutSeconds: _silenceTimeout.round(),
      googleDriveFolderId: _folderIdController.text.trim(),
      googleDocId: _docIdController.text.trim(),
    );

    controller.updateSettings(newSettings);

    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Ajustes guardados correctamente.')),
    );

    Navigator.pop(context);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0F0F1A),
      appBar: AppBar(
        backgroundColor: const Color(0xFF151525),
        title: const Text('AJUSTES Y CONFIGURACIÓN'),
        actions: [
          IconButton(
            icon: const Icon(Icons.save, color: Colors.greenAccent),
            onPressed: _saveAll,
          )
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'CEREBRO IA (MULTI-PROVEEDOR)',
              style: TextStyle(color: Colors.purpleAccent, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                  child: ChoiceChip(
                    label: const Text('Gemini (BLOCK_NONE)'),
                    selected: _activeProvider == 'gemini',
                    selectedColor: Colors.purpleAccent,
                    onSelected: (val) {
                      if (val) setState(() => _activeProvider = 'gemini');
                    },
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: ChoiceChip(
                    label: const Text('DeepSeek API'),
                    selected: _activeProvider == 'deepseek',
                    selectedColor: Colors.blueAccent,
                    onSelected: (val) {
                      if (val) setState(() => _activeProvider = 'deepseek');
                    },
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            TextField(
              controller: _geminiKeyController,
              obscureText: true,
              style: const TextStyle(color: Colors.white),
              decoration: const InputDecoration(
                labelText: 'Gemini API Key (Google AI Studio)',
                labelStyle: TextStyle(color: Colors.white70),
                enabledBorder: OutlineInputBorder(borderSide: BorderSide(color: Colors.white24)),
                focusedBorder: OutlineInputBorder(borderSide: BorderSide(color: Colors.purpleAccent)),
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _deepseekKeyController,
              obscureText: true,
              style: const TextStyle(color: Colors.white),
              decoration: const InputDecoration(
                labelText: 'DeepSeek API Key',
                labelStyle: TextStyle(color: Colors.white70),
                enabledBorder: OutlineInputBorder(borderSide: BorderSide(color: Colors.white24)),
                focusedBorder: OutlineInputBorder(borderSide: BorderSide(color: Colors.blueAccent)),
              ),
            ),
            const Divider(color: Colors.white24, height: 32),
            const Text(
              'PALABRAS CLAVE GATILLO (CONFIGURABLES)',
              style: TextStyle(color: Colors.blueAccent, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 6),
            const Text(
              'Separa por comas las palabras que activarán a la IA mientras hablas:',
              style: TextStyle(color: Colors.white54, fontSize: 12),
            ),
            const SizedBox(height: 8),
            TextField(
              controller: _keywordsController,
              maxLines: 2,
              style: const TextStyle(color: Colors.white),
              decoration: const InputDecoration(
                hintText: 'turno de la ia, opina, debatamos, qué piensas, dale, avanza',
                hintStyle: TextStyle(color: Colors.white24),
                enabledBorder: OutlineInputBorder(borderSide: BorderSide(color: Colors.white24)),
                focusedBorder: OutlineInputBorder(borderSide: BorderSide(color: Colors.blueAccent)),
              ),
            ),
            const SizedBox(height: 20),
            Text(
              'TIEMPO DE SILENCIO PARA GATILLO AUTOMÁTICO: ${_silenceTimeout.round()} seg',
              style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
            ),
            Slider(
              value: _silenceTimeout,
              min: 10,
              max: 30,
              divisions: 20,
              label: '${_silenceTimeout.round()}s',
              activeColor: Colors.blueAccent,
              onChanged: (val) => setState(() => _silenceTimeout = val),
            ),
            const Divider(color: Colors.white24, height: 32),
            const Text(
              'INTEGRACIÓN DRIVE & NOTEBOOKLM',
              style: TextStyle(color: Colors.greenAccent, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _folderIdController,
              style: const TextStyle(color: Colors.white),
              decoration: const InputDecoration(
                labelText: 'ID de Carpeta Pública en Google Drive',
                labelStyle: TextStyle(color: Colors.white70),
                enabledBorder: OutlineInputBorder(borderSide: BorderSide(color: Colors.white24)),
                focusedBorder: OutlineInputBorder(borderSide: BorderSide(color: Colors.greenAccent)),
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _docIdController,
              style: const TextStyle(color: Colors.white),
              decoration: const InputDecoration(
                labelText: 'ID del Google Doc Maestro (Historia_Maestra.gdoc)',
                labelStyle: TextStyle(color: Colors.white70),
                enabledBorder: OutlineInputBorder(borderSide: BorderSide(color: Colors.white24)),
                focusedBorder: OutlineInputBorder(borderSide: BorderSide(color: Colors.greenAccent)),
              ),
            ),
            const SizedBox(height: 16),
            Consumer<SessionController>(
              builder: (context, controller, child) {
                return ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.green.shade800,
                    foregroundColor: Colors.white,
                    minimumSize: const Size(double.infinity, 48),
                  ),
                  onPressed: () async {
                    final ok = await controller.signInGoogle();
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(
                        content: Text(ok ? 'Cuenta de Google conectada.' : 'No se pudo autenticar con Google.'),
                      ),
                    );
                  },
                  icon: const Icon(Icons.account_circle),
                  label: const Text('CONECTAR CUENTA DE GOOGLE'),
                );
              },
            ),
            const SizedBox(height: 24),
            ElevatedButton(
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.purpleAccent,
                foregroundColor: Colors.white,
                minimumSize: const Size(double.infinity, 50),
              ),
              onPressed: _saveAll,
              child: const Text('GUARDAR Y APLICAR', style: TextStyle(fontWeight: FontWeight.bold)),
            ),
          ],
        ),
      ),
    );
  }
}
