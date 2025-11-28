#!/usr/bin/expect -f

# Volensy Quik Gain Otomatik Deployment Script (Expect ile)
# Passphrase otomatik olarak girilir

set timeout 300
set SSH_KEY "$env(HOME)/deneme_oto"
set SSH_HOST "root@139.59.163.105"
set PASSPHRASE "deneme_oto"
set TAR_FILE "/tmp/volensy_quik_gain.tar.gz"
set PROJECT_DIR "/Users/eralpcukurova/volensy_quik_gain/volensy_quik_gain"

puts "🚀 Volensy Quik Gain otomatik kurulum başlatılıyor...\n"

# Projeyi paketle
puts "📦 Proje paketleniyor..."
spawn bash -c "cd $PROJECT_DIR && tar -czf $TAR_FILE --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' --exclude='.env' --exclude='*.tar.gz' --exclude='*.log' ."
expect eof
puts "✅ Paket oluşturuldu: $TAR_FILE\n"

# Dosyaları sunucuya kopyala
puts "📤 Dosyalar sunucuya kopyalanıyor..."
spawn scp -i $SSH_KEY $TAR_FILE $SSH_HOST:/tmp/
expect {
    "Enter passphrase for key" {
        send "$PASSPHRASE\r"
        exp_continue
    }
    "password:" {
        send "$PASSPHRASE\r"
        exp_continue
    }
    eof
}
puts "✅ Dosyalar sunucuya kopyalandı\n"

# Kurulum scriptini sunucuya kopyala
puts "📤 Kurulum scripti kopyalanıyor..."
spawn scp -i $SSH_KEY $PROJECT_DIR/deploy_setup.sh $SSH_HOST:/tmp/
expect {
    "Enter passphrase for key" {
        send "$PASSPHRASE\r"
        exp_continue
    }
    "password:" {
        send "$PASSPHRASE\r"
        exp_continue
    }
    eof
}
puts "✅ Kurulum scripti kopyalandı\n"

# Sunucuda kurulumu çalıştır
puts "🔧 Sunucuda kurulum yapılıyor..."
spawn ssh -i $SSH_KEY $SSH_HOST "chmod +x /tmp/deploy_setup.sh && /tmp/deploy_setup.sh"
expect {
    "Enter passphrase for key" {
        send "$PASSPHRASE\r"
        exp_continue
    }
    "password:" {
        send "$PASSPHRASE\r"
        exp_continue
    }
    eof
}
puts "\n✅ Kurulum tamamlandı!\n"
puts "📁 Proje dizini: /root/volensy_quik_gain\n"
puts "🔧 Sunucuya bağlanmak için:"
puts "   ssh -i $SSH_KEY $SSH_HOST\n"

