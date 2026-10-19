import 'package:flutter/material.dart';

class AppColors {
  static const background = Color(0xFFF7F7F4);
  static const surface = Color(0xFFFFFFFF);
  static const surfaceAlt = Color(0xFFDCECCB);
  static const textPrimary = Color(0xFF222222);
  static const textSecondary = Color(0xFF777777);
  static const accent = Color(0xFF54B80F);
  static const accentDeep = Color(0xFF348A0B);
  static const accentSoft = Color(0xFFDCECCB);
  static const success = Color(0xFF54B80F);
  static const warning = Color(0xFFB26A00);
  static const error = Color(0xFFD93838);
  static const border = Color(0xFFE8E8E3);
}

class AppSpacing {
  static const xs = 4.0;
  static const sm = 8.0;
  static const md = 12.0;
  static const lg = 16.0;
  static const xl = 24.0;
  static const xxl = 32.0;
}

class AppRadii {
  static const sm = 8.0;
  static const md = 12.0;
  static const lg = 16.0;
  static const xl = 24.0;
}

ThemeData buildTheme() {
  final base = ThemeData(
    useMaterial3: true,
    colorScheme: ColorScheme.fromSeed(
      seedColor: AppColors.accent,
      brightness: Brightness.light,
      primary: AppColors.accent,
      onPrimary: Colors.white,
      secondary: AppColors.accentDeep,
      surface: AppColors.surface,
      onSurface: AppColors.textPrimary,
      error: AppColors.error,
    ),
  );
  return base.copyWith(
    scaffoldBackgroundColor: AppColors.background,
    textTheme: base.textTheme.apply(
      bodyColor: AppColors.textPrimary,
      displayColor: AppColors.textPrimary,
    ).copyWith(
      headlineLarge: const TextStyle(fontSize: 32, fontWeight: FontWeight.w700, letterSpacing: -0.5, color: AppColors.textPrimary),
      headlineMedium: const TextStyle(fontSize: 26, fontWeight: FontWeight.w700, letterSpacing: -0.3, color: AppColors.textPrimary),
      headlineSmall: const TextStyle(fontSize: 22, fontWeight: FontWeight.w600, color: AppColors.textPrimary),
      titleLarge: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600, color: AppColors.textPrimary),
      titleMedium: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: AppColors.textPrimary),
      titleSmall: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: AppColors.textPrimary),
      bodyLarge: const TextStyle(fontSize: 16, height: 1.5, color: AppColors.textPrimary),
      bodyMedium: const TextStyle(fontSize: 14, height: 1.5, color: AppColors.textPrimary),
      bodySmall: const TextStyle(fontSize: 12, height: 1.4, color: AppColors.textSecondary),
      labelLarge: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: AppColors.textPrimary),
      labelMedium: const TextStyle(fontSize: 12, fontWeight: FontWeight.w500, color: AppColors.textPrimary),
      labelSmall: const TextStyle(fontSize: 11, fontWeight: FontWeight.w500, color: AppColors.textSecondary),
    ),
     appBarTheme: const AppBarTheme(
       backgroundColor: AppColors.background,
       foregroundColor: AppColors.textPrimary,
       elevation: 0,
       centerTitle: false,
       titleTextStyle: TextStyle(fontSize: 20, fontWeight: FontWeight.w700, color: AppColors.textPrimary),
     ),
     iconTheme: const IconThemeData(color: AppColors.textPrimary),
     primaryIconTheme: const IconThemeData(color: AppColors.textPrimary),
     cardTheme: CardThemeData(
       color: AppColors.surface,
       elevation: 0,
       shape: RoundedRectangleBorder(
         borderRadius: BorderRadius.circular(AppRadii.lg),
         side: const BorderSide(color: AppColors.border),
       ),
       margin: EdgeInsets.zero,
     ),
     dialogTheme: const DialogThemeData(
       backgroundColor: AppColors.surface,
       titleTextStyle: TextStyle(fontSize: 18, fontWeight: FontWeight.w600, color: AppColors.textPrimary),
       contentTextStyle: TextStyle(fontSize: 14, height: 1.5, color: AppColors.textPrimary),
     ),
     snackBarTheme: const SnackBarThemeData(
       backgroundColor: AppColors.textPrimary,
       contentTextStyle: TextStyle(color: Colors.white, fontSize: 14),
       actionTextColor: AppColors.accent,
     ),
     chipTheme: ChipThemeData(
       backgroundColor: AppColors.surface,
       selectedColor: AppColors.accentSoft,
       labelStyle: const TextStyle(color: AppColors.textPrimary),
       secondaryLabelStyle: const TextStyle(color: AppColors.textPrimary),
       brightness: Brightness.light,
     ),
     popupMenuTheme: const PopupMenuThemeData(
       color: AppColors.surface,
       textStyle: TextStyle(color: AppColors.textPrimary),
     ),
     inputDecorationTheme: InputDecorationTheme(
       filled: true,
       fillColor: AppColors.surface,
       contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
       labelStyle: const TextStyle(color: AppColors.textSecondary),
       floatingLabelStyle: const TextStyle(color: AppColors.accent),
       hintStyle: const TextStyle(color: AppColors.textSecondary),
       helperStyle: const TextStyle(color: AppColors.textSecondary),
       errorStyle: const TextStyle(color: AppColors.error),
       prefixIconColor: AppColors.textSecondary,
       suffixIconColor: AppColors.textSecondary,
       border: OutlineInputBorder(
         borderRadius: BorderRadius.circular(AppRadii.md),
         borderSide: const BorderSide(color: AppColors.border),
       ),
       enabledBorder: OutlineInputBorder(
         borderRadius: BorderRadius.circular(AppRadii.md),
         borderSide: const BorderSide(color: AppColors.border),
       ),
       focusedBorder: OutlineInputBorder(
         borderRadius: BorderRadius.circular(AppRadii.md),
         borderSide: const BorderSide(color: AppColors.accent, width: 1.5),
       ),
       errorBorder: OutlineInputBorder(
         borderRadius: BorderRadius.circular(AppRadii.md),
         borderSide: const BorderSide(color: AppColors.error),
       ),
       focusedErrorBorder: OutlineInputBorder(
         borderRadius: BorderRadius.circular(AppRadii.md),
         borderSide: const BorderSide(color: AppColors.error, width: 1.5),
       ),
     ),
    elevatedButtonTheme: ElevatedButtonThemeData(
      style: ElevatedButton.styleFrom(
        backgroundColor: AppColors.textPrimary,
        foregroundColor: Colors.white,
        elevation: 0,
        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(AppRadii.md)),
        textStyle: const TextStyle(fontWeight: FontWeight.w600, fontSize: 15),
      ),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: AppColors.accent,
        foregroundColor: Colors.white,
        elevation: 0,
        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(AppRadii.md)),
        textStyle: const TextStyle(fontWeight: FontWeight.w600, fontSize: 15),
      ),
    ),
     outlinedButtonTheme: OutlinedButtonThemeData(
       style: OutlinedButton.styleFrom(
         foregroundColor: AppColors.textPrimary,
         side: const BorderSide(color: AppColors.border),
         padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
         shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(AppRadii.md)),
       ),
     ),
     bottomSheetTheme: const BottomSheetThemeData(
       backgroundColor: AppColors.surface,
     ),
     dropdownMenuTheme: DropdownMenuThemeData(
       inputDecorationTheme: InputDecorationTheme(
         filled: true,
         fillColor: AppColors.surface,
         labelStyle: const TextStyle(color: AppColors.textSecondary),
         hintStyle: const TextStyle(color: AppColors.textSecondary),
       ),
       textStyle: const TextStyle(color: AppColors.textPrimary),
     ),
     navigationBarTheme: NavigationBarThemeData(
       backgroundColor: AppColors.surface,
       indicatorColor: AppColors.accentSoft,
       labelTextStyle: WidgetStateProperty.all(
         const TextStyle(color: AppColors.textPrimary, fontSize: 12),
       ),
     ),
     navigationRailTheme: const NavigationRailThemeData(
       backgroundColor: AppColors.surface,
       selectedIconTheme: IconThemeData(color: AppColors.accent),
       selectedLabelTextStyle: TextStyle(color: AppColors.accent),
       unselectedLabelTextStyle: TextStyle(color: AppColors.textSecondary),
     ),
  );
}
