class DriverDocument {
  DriverDocument({
    required this.id,
    required this.docType,
    required this.docNumber,
    this.expiryDate,
  });

  final String id;
  final String docType;
  final String docNumber;
  final String? expiryDate;

  factory DriverDocument.fromJson(Map<String, dynamic> json) {
    return DriverDocument(
      id: '${json['id'] ?? ''}',
      docType: '${json['doc_type'] ?? ''}',
      docNumber: '${json['doc_number'] ?? ''}',
      expiryDate: json['expiry_date'] as String?,
    );
  }
}

class DriverProfile {
  DriverProfile({
    required this.id,
    required this.displayName,
    this.fullName,
    this.phone,
    this.whatsappNumber,
    this.alternateNumber,
    this.homeArea,
    this.licenseNumber,
    this.licenseExpiry,
    this.active = true,
    this.verificationStatus = 'unverified',
    this.accountStatus = 'active',
    this.photoUrl,
    List<DriverDocument>? documents,
  }) : documents = documents ?? const [];

  final String id;
  final String displayName;
  final String? fullName;
  final String? phone;
  final String? whatsappNumber;
  final String? alternateNumber;
  final String? homeArea;
  final String? licenseNumber;
  final String? licenseExpiry;
  final bool active;
  final String verificationStatus;
  final String accountStatus;
  final String? photoUrl;
  final List<DriverDocument> documents;

  factory DriverProfile.fromJson(Map<String, dynamic> json) {
    final docs = <DriverDocument>[];
    final raw = json['documents'];
    if (raw is List) {
      for (final item in raw) {
        if (item is Map<String, dynamic>) {
          docs.add(DriverDocument.fromJson(item));
        }
      }
    }
    return DriverProfile(
      id: '${json['id'] ?? ''}',
      displayName: '${json['display_name'] ?? json['full_name'] ?? 'Driver'}',
      fullName: json['full_name'] as String?,
      phone: json['phone'] as String?,
      whatsappNumber: json['whatsapp_number'] as String?,
      alternateNumber: json['alternate_number'] as String?,
      homeArea: json['home_area'] as String?,
      licenseNumber: json['license_number'] as String?,
      licenseExpiry: json['license_expiry'] as String?,
      active: json['active'] != false,
      verificationStatus: '${json['verification_status'] ?? 'unverified'}',
      accountStatus: '${json['account_status'] ?? 'active'}',
      photoUrl: json['photo_url'] as String?,
      documents: docs,
    );
  }
}

class AppNotification {
  AppNotification({
    required this.id,
    required this.kind,
    required this.title,
    required this.body,
    this.readAt,
    this.createdAt,
    this.bookingId,
    this.assignmentId,
  });

  final String id;
  final String kind;
  final String title;
  final String body;
  final String? readAt;
  final String? createdAt;
  final String? bookingId;
  final String? assignmentId;

  bool get isUnread => readAt == null || readAt!.isEmpty;

  factory AppNotification.fromJson(Map<String, dynamic> json) {
    return AppNotification(
      id: '${json['id'] ?? ''}',
      kind: '${json['kind'] ?? ''}',
      title: '${json['title'] ?? ''}',
      body: '${json['body'] ?? ''}',
      readAt: json['read_at'] as String?,
      createdAt: json['created_at'] as String?,
      bookingId: json['booking_id'] as String?,
      assignmentId: json['assignment_id'] as String?,
    );
  }
}

class PayoutItem {
  PayoutItem({
    required this.id,
    required this.bookingReference,
    required this.amount,
    required this.status,
    this.dutyDate,
    this.paidAt,
    this.reference,
    this.currency = 'INR',
  });

  final String id;
  final String bookingReference;
  final double amount;
  final String status;
  final String? dutyDate;
  final String? paidAt;
  final String? reference;
  final String currency;

  factory PayoutItem.fromJson(Map<String, dynamic> json) {
    final amountRaw = json['amount'];
    return PayoutItem(
      id: '${json['id'] ?? ''}',
      bookingReference: '${json['booking_reference'] ?? json['booking_id'] ?? ''}',
      amount: amountRaw is num
          ? amountRaw.toDouble()
          : double.tryParse('$amountRaw') ?? 0,
      status: '${json['status'] ?? ''}',
      dutyDate: json['duty_date'] as String?,
      paidAt: json['paid_at'] as String?,
      reference: json['reference'] as String?,
      currency: '${json['currency'] ?? 'INR'}',
    );
  }
}
