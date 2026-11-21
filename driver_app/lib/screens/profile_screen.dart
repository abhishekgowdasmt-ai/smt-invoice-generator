import 'package:material_ui/material_ui.dart';
import 'package:provider/provider.dart';

import '../state/auth_controller.dart';
import '../widgets/status_chip.dart';

class ProfileScreen extends StatelessWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthController>();
    final profile = auth.profile;
    if (profile == null) {
      return const Center(child: Text('Profile unavailable'));
    }
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(profile.displayName, style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w700)),
                const SizedBox(height: 8),
                Wrap(
                  spacing: 8,
                  children: [
                    StatusChip(profile.verificationStatus, status: profile.verificationStatus),
                    StatusChip(
                      profile.active ? 'active' : 'inactive',
                      status: profile.active ? 'active' : 'disabled',
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                _row('Phone', profile.phone),
                _row('WhatsApp', profile.whatsappNumber),
                _row('Alternate', profile.alternateNumber),
                _row('Home area', profile.homeArea),
                _row('Licence', profile.licenseNumber),
                _row('Licence expiry', profile.licenseExpiry),
              ],
            ),
          ),
        ),
        const SizedBox(height: 12),
        const Text('Documents', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
        const SizedBox(height: 8),
        if (profile.documents.isEmpty)
          const Text(
            'No document metadata on file. File uploads are not enabled in this release.',
            style: TextStyle(color: Color(0xFF5C6670)),
          )
        else
          ...profile.documents.map(
            (doc) => Card(
              child: ListTile(
                title: Text(doc.docType),
                subtitle: Text(
                  [
                    doc.docNumber,
                    if (doc.expiryDate != null) 'Expires ${doc.expiryDate}',
                  ].join(' · '),
                ),
              ),
            ),
          ),
        const SizedBox(height: 24),
        OutlinedButton(
          onPressed: () => auth.logout(),
          child: const Text('Sign out'),
        ),
      ],
    );
  }

  Widget _row(String label, String? value) {
    if (value == null || value.isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        children: [
          SizedBox(width: 120, child: Text(label, style: const TextStyle(color: Color(0xFF5C6670)))),
          Expanded(child: Text(value)),
        ],
      ),
    );
  }
}
