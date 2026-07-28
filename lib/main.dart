import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'providers/session_controller.dart';
import 'screens/driving_mode_screen.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final sessionController = SessionController();
  await sessionController.initSession();

  runApp(
    ChangeNotifierProvider.value(
      value: sessionController,
      child: const CoEscritorApp(),
    ),
  );
}

class CoEscritorApp extends StatelessWidget {
  const CoEscritorApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Co-Escritor IA (Modo Manejo)',
      debugShowCheckedModeBanner: false,
      theme: ThemeData.dark().copyWith(
        scaffoldBackgroundColor: const Color(0xFF0F0F1A),
        primaryColor: Colors.purpleAccent,
        colorScheme: const ColorScheme.dark(
          primary: Colors.purpleAccent,
          secondary: Colors.blueAccent,
          surface: Color(0xFF151525),
        ),
      ),
      home: const DrivingModeScreen(),
    );
  }
}
