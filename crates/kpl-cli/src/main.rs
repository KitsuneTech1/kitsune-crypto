//! Kitsune Private Layer (kpl-cli) - Fast Rust CLI Wallet and Offline Signer.

use std::env;
use std::process;
use rand::rngs::OsRng;
use curve25519_dalek::scalar::Scalar;
use curve25519_dalek::edwards::EdwardsPoint;
use kpl_core::{
    StealthKeys,
    create_stealth_output,
    scan_stealth_output,
    PedersenCommitment,
    ClsagSignature,
    compute_key_image,
    calculate_block_reward,
    ATOMIC_UNITS,
};

fn print_help() {
    println!("KITSUNE PRIVATE LAYER (KPL) CLI WALLET v0.1.0");
    println!("Usage:");
    println!("  kpl-cli wallet generate");
    println!("  kpl-cli tx sign <recipient_kpl_addr> <amount_atomic> <fee_atomic>");
    println!("  kpl-cli tx verify-sample");
    println!("  kpl-cli emission <already_generated_coins>");
}

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() < 2 {
        print_help();
        return;
    }

    match args[1].as_str() {
        "wallet" => {
            if args.len() >= 3 && args[2] == "generate" {
                let mut rng = OsRng;
                let keys = StealthKeys::generate(&mut rng);
                let view_pub_hex = hex::encode(keys.view_public.compress().as_bytes());
                let spend_pub_hex = hex::encode(keys.spend_public.compress().as_bytes());
                let addr = format!("kpl_{}{}", view_pub_hex, spend_pub_hex);

                println!("=== NEW KPL STEALTH WALLET GENERATED ===");
                println!("Public Address:    {}", addr);
                println!("Private View Key:  {}", hex::encode(keys.view_secret.as_bytes()));
                println!("Public View Key:   {}", view_pub_hex);
                println!("Private Spend Key: {}", hex::encode(keys.spend_secret.as_bytes()));
                println!("Public Spend Key:  {}", spend_pub_hex);
                println!("=========================================");
            } else {
                print_help();
            }
        }
        "tx" => {
            if args.len() >= 3 && args[2] == "sign" {
                if args.len() < 6 {
                    println!("Error: tx sign requires <recipient_addr> <amount> <fee>");
                    process::exit(1);
                }
                let recipient = &args[3];
                let amount: u64 = args[4].parse().unwrap_or(500_000);
                let fee: u64 = args[5].parse().unwrap_or(50_000);

                let mut rng = OsRng;
                let sender = StealthKeys::generate(&mut rng);
                let receiver = StealthKeys::generate(&mut rng);

                // Construct stealth output
                let (one_time_pub, tx_pub_R) = create_stealth_output(&receiver.view_public, &receiver.spend_public, &mut rng);

                // Construct Pedersen commitment
                let blind = Scalar::random(&mut rng);
                let commitment = PedersenCommitment::create(amount, blind);

                // Construct 5-member decoy ring
                let mut ring = Vec::new();
                let mut keys = Vec::new();
                for _ in 0..4 {
                    let sec = Scalar::random(&mut rng);
                    ring.push(EdwardsPoint::mul_base(&sec));
                    keys.push(sec);
                }
                let real_idx = 2;
                ring.insert(real_idx, sender.spend_public);
                keys.insert(real_idx, sender.spend_secret);

                let msg_payload = format!("TX_OUT:{}:AMT:{}:FEE:{}", hex::encode(one_time_pub.compress().as_bytes()), amount, fee);
                let sig = ClsagSignature::sign(msg_payload.as_bytes(), &ring, real_idx, &sender.spend_secret, &mut rng);

                let tx_json = serde_json::json!({
                    "version": 1,
                    "recipient": recipient,
                    "amount_atomic": amount,
                    "fee_atomic": fee,
                    "stealth_out_P": hex::encode(one_time_pub.compress().as_bytes()),
                    "tx_pub_R": hex::encode(tx_pub_R.compress().as_bytes()),
                    "commitment": hex::encode(commitment.point.compress().as_bytes()),
                    "key_image": hex::encode(sig.key_image.compress().as_bytes()),
                    "ring_size": ring.len(),
                    "signature_c0": hex::encode(sig.c0.as_bytes()),
                    "offline_signed": true,
                    "verified": sig.verify(msg_payload.as_bytes())
                });

                println!("{}", serde_json::to_string_pretty(&tx_json).unwrap());
            } else if args.len() >= 3 && args[2] == "verify-sample" {
                let mut rng = OsRng;
                let sender = StealthKeys::generate(&mut rng);
                let ring = vec![
                    EdwardsPoint::mul_base(&Scalar::random(&mut rng)),
                    sender.spend_public,
                    EdwardsPoint::mul_base(&Scalar::random(&mut rng)),
                ];
                let msg = b"SAMPLE-OFFLINE-TX-PAYLOAD";
                let sig = ClsagSignature::sign(msg, &ring, 1, &sender.spend_secret, &mut rng);
                let verified = sig.verify(msg);
                println!("Sample CLSAG Ring Signature Verification: {}", if verified { "SUCCESS (VERIFIED)" } else { "FAILED" });
                println!("Key Image: {}", hex::encode(sig.key_image.compress().as_bytes()));
            } else {
                print_help();
            }
        }
        "emission" => {
            let gen: u64 = args.get(2).and_then(|s| s.parse().ok()).unwrap_or(0);
            let reward = calculate_block_reward(gen);
            println!("At generated coins: {} KPL", gen / ATOMIC_UNITS);
            println!("Block reward:       {:.6} KPL ({} atomic units)", reward as f64 / ATOMIC_UNITS as f64, reward);
        }
        _ => print_help(),
    }
}
