import 'package:material_ui/material_ui.dart';
import 'package:provider/provider.dart';

import '../config/app_config.dart';
import '../state/auth_controller.dart';

enum _AuthMode { password, otp, reset }

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _phone = TextEditingController();
  final _password = TextEditingController();
  final _otp = TextEditingController();
  final _newPassword = TextEditingController();
  final _formKey = GlobalKey<FormState>();
  _AuthMode _mode = _AuthMode.password;
  bool _otpSent = false;
  String? _hint;

  @override
  void dispose() {
    _phone.dispose();
    _password.dispose();
    _otp.dispose();
    _newPassword.dispose();
    super.dispose();
  }

  void _setMode(_AuthMode mode) {
    setState(() {
      _mode = mode;
      _otpSent = false;
      _otp.clear();
      _newPassword.clear();
      _hint = null;
    });
  }

  String? _validatePhone(String? value) {
    final digits = (value ?? '').replaceAll(RegExp(r'\D'), '');
    if (digits.length != 10 && !(digits.length == 12 && digits.startsWith('91'))) {
      return 'Enter a valid 10-digit phone';
    }
    return null;
  }

  Future<void> _requestOtp(String purpose) async {
    if (_validatePhone(_phone.text) != null) {
      _formKey.currentState?.validate();
      return;
    }
    final auth = context.read<AuthController>();
    final result = await auth.requestOtp(_phone.text.trim(), purpose);
    if (!mounted) return;
    if (result == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(auth.errorMessage ?? 'Could not send OTP')),
      );
      return;
    }
    setState(() {
      _otpSent = true;
      _hint = result['message'] as String? ?? 'OTP sent on WhatsApp.';
      final devCode = result['dev_code'];
      if (devCode is String && devCode.isNotEmpty) {
        _otp.text = devCode;
        _hint = '$_hint (dev code filled)';
      }
    });
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    final auth = context.read<AuthController>();
    final phone = _phone.text.trim();

    if (_mode == _AuthMode.password) {
      final ok = await auth.login(phone, _password.text);
      if (!ok && mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(auth.errorMessage ?? 'Sign-in failed')),
        );
      }
      return;
    }

    if (_mode == _AuthMode.otp) {
      if (!_otpSent) {
        await _requestOtp('login');
        return;
      }
      final ok = await auth.loginWithOtp(phone, _otp.text.trim());
      if (!ok && mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(auth.errorMessage ?? 'OTP sign-in failed')),
        );
      }
      return;
    }

    // reset
    if (!_otpSent) {
      await _requestOtp('reset');
      return;
    }
    final ok = await auth.resetPasswordWithOtp(
      phone: phone,
      code: _otp.text.trim(),
      newPassword: _newPassword.text,
    );
    if (!mounted) return;
    if (!ok) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(auth.errorMessage ?? 'Password reset failed')),
      );
      return;
    }
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Password updated. Sign in with the new password.')),
    );
    _password.text = _newPassword.text;
    _setMode(_AuthMode.password);
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthController>();
    final primaryLabel = switch (_mode) {
      _AuthMode.password => 'Sign in',
      _AuthMode.otp => _otpSent ? 'Verify OTP' : 'Send OTP',
      _AuthMode.reset => _otpSent ? 'Update password' : 'Send reset OTP',
    };

    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [Color(0xFF1B4332), Color(0xFF2D6A4F), Color(0xFFF7F3EB)],
            stops: [0, 0.45, 0.45],
          ),
        ),
        child: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(24),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 420),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const Text(
                      AppConfig.appName,
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 28,
                        fontWeight: FontWeight.w800,
                        height: 1.2,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      switch (_mode) {
                        _AuthMode.password => 'Driver sign-in',
                        _AuthMode.otp => 'Sign in with OTP',
                        _AuthMode.reset => 'Reset password',
                      },
                      textAlign: TextAlign.center,
                      style: const TextStyle(color: Colors.white70, fontSize: 16),
                    ),
                    const SizedBox(height: 32),
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.all(20),
                        child: Form(
                          key: _formKey,
                          child: Column(
                            children: [
                              if (_mode != _AuthMode.reset)
                                Row(
                                  children: [
                                    Expanded(
                                      child: OutlinedButton(
                                        onPressed: auth.busy
                                            ? null
                                            : () => _setMode(_AuthMode.password),
                                        style: OutlinedButton.styleFrom(
                                          backgroundColor: _mode == _AuthMode.password
                                              ? const Color(0xFF2D6A4F)
                                              : null,
                                          foregroundColor: _mode == _AuthMode.password
                                              ? Colors.white
                                              : null,
                                        ),
                                        child: const Text('Password'),
                                      ),
                                    ),
                                    const SizedBox(width: 8),
                                    Expanded(
                                      child: OutlinedButton(
                                        onPressed: auth.busy
                                            ? null
                                            : () => _setMode(_AuthMode.otp),
                                        style: OutlinedButton.styleFrom(
                                          backgroundColor: _mode == _AuthMode.otp
                                              ? const Color(0xFF2D6A4F)
                                              : null,
                                          foregroundColor: _mode == _AuthMode.otp
                                              ? Colors.white
                                              : null,
                                        ),
                                        child: const Text('OTP'),
                                      ),
                                    ),
                                  ],
                                ),
                              if (_mode != _AuthMode.reset) const SizedBox(height: 16),
                              TextFormField(
                                controller: _phone,
                                keyboardType: TextInputType.phone,
                                decoration: const InputDecoration(
                                  labelText: 'Phone number',
                                  hintText: '10-digit mobile',
                                ),
                                validator: _validatePhone,
                              ),
                              if (_mode == _AuthMode.password) ...[
                                const SizedBox(height: 12),
                                TextFormField(
                                  controller: _password,
                                  obscureText: true,
                                  decoration: const InputDecoration(labelText: 'Password'),
                                  validator: (value) {
                                    if ((value ?? '').length < 8) {
                                      return 'Password must be at least 8 characters';
                                    }
                                    return null;
                                  },
                                ),
                              ],
                              if (_mode == _AuthMode.otp && _otpSent) ...[
                                const SizedBox(height: 12),
                                TextFormField(
                                  controller: _otp,
                                  keyboardType: TextInputType.number,
                                  decoration: const InputDecoration(
                                    labelText: 'OTP code',
                                    hintText: '6-digit code from WhatsApp',
                                  ),
                                  validator: (value) {
                                    final digits = (value ?? '').trim();
                                    if (!RegExp(r'^\d{6}$').hasMatch(digits)) {
                                      return 'Enter the 6-digit OTP';
                                    }
                                    return null;
                                  },
                                ),
                              ],
                              if (_mode == _AuthMode.reset) ...[
                                if (_otpSent) ...[
                                  const SizedBox(height: 12),
                                  TextFormField(
                                    controller: _otp,
                                    keyboardType: TextInputType.number,
                                    decoration: const InputDecoration(
                                      labelText: 'OTP code',
                                      hintText: '6-digit code from WhatsApp',
                                    ),
                                    validator: (value) {
                                      final digits = (value ?? '').trim();
                                      if (!RegExp(r'^\d{6}$').hasMatch(digits)) {
                                        return 'Enter the 6-digit OTP';
                                      }
                                      return null;
                                    },
                                  ),
                                  const SizedBox(height: 12),
                                  TextFormField(
                                    controller: _newPassword,
                                    obscureText: true,
                                    decoration: const InputDecoration(
                                      labelText: 'New password',
                                    ),
                                    validator: (value) {
                                      if ((value ?? '').length < 8) {
                                        return 'Password must be at least 8 characters';
                                      }
                                      return null;
                                    },
                                  ),
                                ],
                              ],
                              if (_hint != null) ...[
                                const SizedBox(height: 12),
                                Text(
                                  _hint!,
                                  style: TextStyle(
                                    color: Colors.grey.shade700,
                                    fontSize: 13,
                                  ),
                                ),
                              ],
                              const SizedBox(height: 20),
                              ElevatedButton(
                                onPressed: auth.busy ? null : _submit,
                                child: auth.busy
                                    ? const SizedBox(
                                        height: 22,
                                        width: 22,
                                        child: CircularProgressIndicator(
                                          strokeWidth: 2,
                                          color: Colors.white,
                                        ),
                                      )
                                    : Text(primaryLabel),
                              ),
                              if (_mode == _AuthMode.password)
                                TextButton(
                                  onPressed: auth.busy ? null : () => _setMode(_AuthMode.reset),
                                  child: const Text('Forgot password?'),
                                ),
                              if (_mode == _AuthMode.reset)
                                TextButton(
                                  onPressed:
                                      auth.busy ? null : () => _setMode(_AuthMode.password),
                                  child: const Text('Back to password sign-in'),
                                ),
                              if (_mode != _AuthMode.password && _otpSent)
                                TextButton(
                                  onPressed: auth.busy
                                      ? null
                                      : () => _requestOtp(
                                            _mode == _AuthMode.reset ? 'reset' : 'login',
                                          ),
                                  child: const Text('Resend OTP'),
                                ),
                            ],
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
