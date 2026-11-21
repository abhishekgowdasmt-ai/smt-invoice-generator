import 'package:material_ui/material_ui.dart';

class AppTheme {
  static const Color forest = Color(0xFF1B4332);
  static const Color leaf = Color(0xFF2D6A4F);
  static const Color sand = Color(0xFFF7F3EB);
  static const Color ink = Color(0xFF1A1A1A);
  static const Color muted = Color(0xFF5C6670);
  static const Color danger = Color(0xFF9B2226);
  static const Color warning = Color(0xFFBC6C25);
  static const Color success = Color(0xFF2A9D8F);

  static ThemeData light() {
    final base = ColorScheme.fromSeed(
      seedColor: leaf,
      primary: forest,
      secondary: leaf,
      surface: sand,
      brightness: Brightness.light,
    );
    return ThemeData(
      useMaterial3: true,
      colorScheme: base,
      scaffoldBackgroundColor: sand,
      appBarTheme: const AppBarTheme(
        backgroundColor: forest,
        foregroundColor: Colors.white,
        elevation: 0,
        centerTitle: false,
      ),
      bottomNavigationBarTheme: const BottomNavigationBarThemeData(
        backgroundColor: Colors.white,
        selectedItemColor: forest,
        unselectedItemColor: muted,
        type: BottomNavigationBarType.fixed,
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: Colors.white,
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: forest,
          foregroundColor: Colors.white,
          minimumSize: const Size.fromHeight(48),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        ),
      ),
      cardTheme: CardThemeData(
        color: Colors.white,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: BorderSide(color: Colors.black.withValues(alpha: 0.06)),
        ),
      ),
    );
  }

  static Color statusColor(String? status) {
    switch ((status ?? '').toLowerCase()) {
      case 'assigned':
      case 'pending':
        return warning;
      case 'accepted':
      case 'started':
      case 'active':
      case 'paid':
      case 'verified':
        return success;
      case 'rejected':
      case 'cancelled':
      case 'withdrawn':
      case 'superseded':
      case 'disabled':
        return danger;
      case 'completed':
        return leaf;
      default:
        return muted;
    }
  }
}
