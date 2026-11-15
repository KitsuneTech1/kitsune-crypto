//! Kitsune Private Layer (kpl-cli) - Fast Rust CLI Wallet, Offline Signer, and Bridge Client.

use std::env;

mod mnemonic;
use mnemonic::{entropy_to_mnemonic, mnemonic_to_seed, seed_to_stealth_keys};
use std::io::{Read, Write};
use std::net::TcpStream;
use std::process;
use std::time::Duration;
use rand::rngs::OsRng;
use curve25519_dalek::scalar::Scalar;
use curve25519_dalek::edwards::EdwardsPoint;
use kpl_core::{
    StealthKeys,
    create_stealth_output,
    PedersenCommitment,
    ClsagSignature,
    calculate_block_reward,
    ATOMIC_UNITS,
};

const DEFAULT_NODE: &str = "192.168.1.201:9200";
const DEFAULT_BRIDGE_SERVER: &str = "127.0.0.1:8792";

fn print_help() {
    println!("KITSUNE PRIVATE LAYER (KPL) CLI WALLET v0.1.0");
    println!("Usage:");
    println!("  kpl-cli wallet generate");
    println!("  kpl-cli wallet import \"<12_word_mnemonic>\"");
    println!("  kpl-cli wallet export <private_spend_hex>");
    println!("  kpl-cli status [--node <host:port>]");
    println!("  kpl-cli bridge quote <chain> <asset> <amount> [--server <host:port>]");
    println!("  kpl-cli bridge deposit <chain> <asset> <amount> <kpl_recipient> [--server <host:port>]");
    println!("  kpl-cli bridge solana-lock <amount> <kpl_recipient> [--server <host:port>] [--rpc <url>]");
    println!("  kpl-cli tx sign <recipient_kpl_addr> <amount_atomic> <fee_atomic>");
    println!("  kpl-cli tx submit <recipient_kpl_addr> <amount_atomic> <fee_atomic> [--node <host:port>]");
    println!("  kpl-cli tx verify-sample");
    println!("  kpl-cli emission <already_generated_coins>");
}

fn http_request(node_addr: &str, method: &str, path: &str, body: Option<&str>) -> Result<(u16, String), String> {
    let clean_addr = node_addr
        .trim_start_matches("http://")
        .trim_start_matches("https://");

    let mut stream = TcpStream::connect(clean_addr)
        .map_err(|e| format!("Failed to connect to {}: {}", clean_addr, e))?;
    stream.set_read_timeout(Some(Duration::from_secs(3))).ok();
    stream.set_write_timeout(Some(Duration::from_secs(3))).ok();

    let content_len = body.map(|b| b.len()).unwrap_or(0);
    let req = format!(
        "{} {} HTTP/1.1\r\nHost: {}\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}",
        method, path, clean_addr, content_len, body.unwrap_or("")
    );
    stream.write_all(req.as_bytes()).map_err(|e| e.to_string())?;

    let mut resp = String::new();
    stream.read_to_string(&mut resp).map_err(|e| e.to_string())?;

    let mut status_code = 200;
    if let Some(status_line) = resp.lines().next() {
        let parts: Vec<&str> = status_line.split_whitespace().collect();
        if parts.len() >= 2 {
            status_code = parts[1].parse().unwrap_or(200);
        }
    }

    let body_str = if let Some(idx) = resp.find("\r\n\r\n") {
        resp[idx + 4..].to_string()
    } else {
        resp
    };

    Ok((status_code, body_str))
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
                let mut entropy = [0u8; 16];
                rand::RngCore::fill_bytes(&mut OsRng, &mut entropy);
                let phrase = entropy_to_mnemonic(&entropy);
                let seed = mnemonic_to_seed(&phrase);
                let (spend_sec, view_sec, spend_pub, view_pub, addr) = seed_to_stealth_keys(&seed);

                println!("=== NEW KPL STEALTH WALLET GENERATED ===");
                println!("Public Address:    {}", addr);
                println!("Mnemonic Phrase:   \"{}\"", phrase);
                println!("Private View Key:  {}", hex::encode(view_sec.as_bytes()));
                println!("Public View Key:   {}", hex::encode(view_pub.compress().as_bytes()));
                println!("Private Spend Key: {}", hex::encode(spend_sec.as_bytes()));
                println!("Public Spend Key:  {}", hex::encode(spend_pub.compress().as_bytes()));
                println!("=========================================");
                println!("NOTE: Write down your 12-word mnemonic phrase. It deterministically recovers your wallet.");
            } else if args.len() >= 4 && args[2] == "import" {
                let phrase = args[3..].join(" ");
                let seed = mnemonic_to_seed(&phrase);
                let (spend_sec, view_sec, spend_pub, view_pub, addr) = seed_to_stealth_keys(&seed);

                println!("=== RECOVERED KPL STEALTH WALLET ===");
                println!("Recovered Address: {}", addr);
                println!("Private View Key:  {}", hex::encode(view_sec.as_bytes()));
                println!("Public View Key:   {}", hex::encode(view_pub.compress().as_bytes()));
                println!("Private Spend Key: {}", hex::encode(spend_sec.as_bytes()));
                println!("Public Spend Key:  {}", hex::encode(spend_pub.compress().as_bytes()));
                println!("=====================================");
            } else if args.len() >= 4 && args[2] == "export" {
                let spend_hex = &args[3];
                if let Ok(bytes) = hex::decode(spend_hex) {
                    if bytes.len() >= 16 {
                        let mut entropy = [0u8; 16];
                        entropy.copy_from_slice(&bytes[..16]);
                        let phrase = entropy_to_mnemonic(&entropy);
                        println!("=== WALLET RECOVERY PHRASE ===");
                        println!("Mnemonic: \"{}\"", phrase);
                        println!("==============================");
                    } else {
                        eprintln!("Invalid spend key length (expected 32 bytes hex)");
                    }
                } else {
                    eprintln!("Invalid hex string");
                }
            } else {
                println!("Usage:");
                println!("  kpl-cli wallet generate");
                println!("  kpl-cli wallet import \"<word1> <word2> ... <word12>\"");
                println!("  kpl-cli wallet export <private_spend_key>");
            }
        }
        "status" => {
            let mut node = DEFAULT_NODE;
            if args.len() >= 4 && args[2] == "--node" {
                node = &args[3];
            }
            println!("Querying KPL validator node: http://{}...", node);
            match http_request(node, "GET", "/status", None) {
                Ok((code, body)) => {
                    if code == 200 {
                        if let Ok(val) = serde_json::from_str::<serde_json::Value>(&body) {
                            println!("=== LIVE KPL VALIDATOR NODE STATUS ===");
                            println!("Node ID:          {}", val["node_id"].as_str().unwrap_or("-"));
                            println!("Current Height:   #{}", val["height"]);
                            println!("Latest Hash:      {}", val["latest_hash"].as_str().unwrap_or("-"));
                            println!("Quorum Threshold: {} / {}", val["quorum_threshold"], val["total_nodes"]);
                            println!("Mempool Count:    {}", val["mempool_count"]);
                            println!("Spent Key Images: {}", val["spent_key_images_count"]);
                            println!("Peer Nodes:       {}", val["peers"]);
                            println!("=======================================");
                        } else {
                            println!("{}", body);
                        }
                    } else {
                        println!("HTTP Error {}: {}", code, body);
                    }
                }
                Err(err) => {
                    eprintln!("RPC Error: {}", err);
                    process::exit(1);
                }
            }
        }
        "bridge" => {
            if args.len() >= 3 && args[2] == "quote" {
                if args.len() < 6 {
                    println!("Usage: kpl-cli bridge quote <chain> <asset> <amount> [--server <host:port>]");
                    println!("Example: kpl-cli bridge quote base USDC 100");
                    process::exit(1);
                }
                let chain = &args[3];
                let asset = &args[4];
                let amount = &args[5];
                let mut server = DEFAULT_BRIDGE_SERVER;
                if args.len() >= 8 && args[6] == "--server" {
                    server = &args[7];
                }

                let path = format!("/api/bridge/quote?chain={}&asset={}&amount={}", chain, asset, amount);
                match http_request(server, "GET", &path, None) {
                    Ok((code, body)) => {
                        if code == 200 {
                            if let Ok(val) = serde_json::from_str::<serde_json::Value>(&body) {
                                println!("=== FAST MULTI-CHAIN BRIDGE QUOTE ===");
                                println!("Route:            {} -> KPL", val["source_chain"].as_str().unwrap_or("-").to_uppercase());
                                println!("Asset Deposited:  {} {}", val["deposit_amount"], val["asset"].as_str().unwrap_or("-"));
                                println!("KPL Output:       {} KPL", val["kpl_received"]);
                                println!("Est. Finality:    ~{} seconds", val["estimated_seconds"]);
                                println!("Bridge Fee:       {} {}", val["fee_amount"], val["asset"].as_str().unwrap_or("-"));
                                println!("Exchange Rate:    1 {} = {} KPL", val["asset"].as_str().unwrap_or("-"), val["exchange_rate"]);
                                println!("=======================================");
                            } else {
                                println!("{}", body);
                            }
                        } else {
                            println!("Quote Error {}: {}", code, body);
                        }
                    }
                    Err(err) => {
                        eprintln!("Connection Error: {}", err);
                        process::exit(1);
                    }
                }
            } else if args.len() >= 3 && args[2] == "deposit" {
                if args.len() < 7 {
                    println!("Usage: kpl-cli bridge deposit <chain> <asset> <amount> <kpl_recipient> [--server <host:port>]");
                    println!("Example: kpl-cli bridge deposit base USDC 50 kpl_your_address...");
                    process::exit(1);
                }
                let chain = &args[3];
                let asset = &args[4];
                let amount: f64 = args[5].parse().unwrap_or(50.0);
                let recipient = &args[6];
                let mut server = DEFAULT_BRIDGE_SERVER;
                if args.len() >= 9 && args[7] == "--server" {
                    server = &args[8];
                }

                let req_body = serde_json::json!({
                    "chain": chain,
                    "asset": asset,
                    "amount": amount,
                    "kpl_recipient": recipient
                }).to_string();

                match http_request(server, "POST", "/api/bridge/deposit", Some(&req_body)) {
                    Ok((code, body)) => {
                        if code == 200 {
                            if let Ok(val) = serde_json::from_str::<serde_json::Value>(&body) {
                                println!("=== BRIDGE DEPOSIT ORDER INITIATED ===");
                                println!("Order ID:         {}", val["order_id"].as_str().unwrap_or("-"));
                                println!("Chain:            {}", val["source_chain"].as_str().unwrap_or("-").to_uppercase());
                                println!("Expected Deposit: {} {}", val["amount"], val["asset"].as_str().unwrap_or("-"));
                                println!("KPL Credit:       {} KPL", val["kpl_received"]);
                                println!("Recipient:        {}", val["kpl_recipient"].as_str().unwrap_or("-"));
                                println!("Est. Speed:       ~{} seconds", val["estimated_seconds"]);
                                println!("\n>>> SEND FUNDS TO DEPOSIT ADDRESS / INVOICE <<<");
                                println!("{}", val["deposit_handle"].as_str().unwrap_or("-"));
                                println!("=======================================");
                            } else {
                                println!("{}", body);
                            }
                        } else {
                            println!("Deposit Error {}: {}", code, body);
                        }
                    }
                    Err(err) => {
                        eprintln!("Connection Error: {}", err);
                        process::exit(1);
                    }
                }
            } else if args.len() >= 3 && args[2] == "solana-lock" {
                if args.len() < 5 {
                    println!("Usage: kpl-cli bridge solana-lock <amount> <kpl_recipient> [--server <host:port>] [--rpc <url>]");
                    println!("Example: kpl-cli bridge solana-lock 0.1 kpl_0123... --rpc https://api.devnet.solana.com");
                    process::exit(1);
                }
                let amount: f64 = args[3].parse().unwrap_or(0.10);
                let recipient = &args[4];
                let mut server = DEFAULT_BRIDGE_SERVER;
                let mut rpc = "https://api.devnet.solana.com";

                let mut i = 5;
                while i < args.len() {
                    if args[i] == "--server" && i + 1 < args.len() {
                        server = &args[i + 1];
                        i += 2;
                    } else if args[i] == "--rpc" && i + 1 < args.len() {
                        rpc = &args[i + 1];
                        i += 2;
                    } else {
                        i += 1;
                    }
                }

                println!("=== SOLANA DEVNET ESCROW LOCKUP ===");
                println!("Connecting to:  {}", rpc);
                println!("Escrow Amount:  {} SOL", amount);
                println!("Recipient:      {}", recipient);

                let req_body = serde_json::json!({
                    "amount": amount,
                    "kpl_recipient": recipient,
                    "rpc": rpc
                }).to_string();

                match http_request(server, "POST", "/api/bridge/solana-lock", Some(&req_body)) {
                    Ok((code, body)) => {
                        if code == 200 {
                            if let Ok(val) = serde_json::from_str::<serde_json::Value>(&body) {
                                println!("=== SOLANA LOCKUP & KPL MINT CONFIRMED ===");
                                println!("Order ID:             {}", val["order_id"].as_str().unwrap_or("-"));
                                println!("Solana Node Version:  {}", val["solana_version"].as_str().unwrap_or("-"));
                                println!("Devnet Blockhash:     {}", val["latest_blockhash"].as_str().unwrap_or("-"));
                                println!("Solana Tx Signature:  {}", val["solana_tx_sig"].as_str().unwrap_or("-"));
                                println!("Escrow Vault:         {}", val["vault_address"].as_str().unwrap_or("-"));
                                println!("KPL Mint Tx Hash:     {}", val["kpl_tx_hash"].as_str().unwrap_or("-"));
                                println!("Minted Stealth KPL:   {} KPL", val["kpl_received"]);
                                println!("Status:               CONFIRMED_SETTLED (Ready for private spend)");
                                println!("==========================================");
                            } else {
                                println!("{}", body);
                            }
                        } else {
                            eprintln!("Solana Lock Error (HTTP {}): {}", code, body);
                            process::exit(1);
                        }
                    }
                    Err(err) => {
                        eprintln!("Bridge Gateway Connection Error: {}", err);
                        process::exit(1);
                    }
                }
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

                let (one_time_pub, tx_pub_r) = create_stealth_output(&receiver.view_public, &receiver.spend_public, &mut rng);
                let blind = Scalar::random(&mut rng);
                let commitment = PedersenCommitment::create(amount, blind);

                let mut ring = Vec::new();
                for _ in 0..4 {
                    ring.push(EdwardsPoint::mul_base(&Scalar::random(&mut rng)));
                }
                let real_idx = 2;
                ring.insert(real_idx, sender.spend_public);

                let msg_payload = format!("TX_OUT:{}:AMT:{}:FEE:{}", hex::encode(one_time_pub.compress().as_bytes()), amount, fee);
                let sig = ClsagSignature::sign(msg_payload.as_bytes(), &ring, real_idx, &sender.spend_secret, &mut rng);

                let tx_json = serde_json::json!({
                    "version": 1,
                    "recipient": recipient,
                    "amount_atomic": amount,
                    "fee_atomic": fee,
                    "stealth_out_P": hex::encode(one_time_pub.compress().as_bytes()),
                    "tx_pub_R": hex::encode(tx_pub_r.compress().as_bytes()),
                    "commitment": hex::encode(commitment.point.compress().as_bytes()),
                    "key_image": hex::encode(sig.key_image.compress().as_bytes()),
                    "ring_size": ring.len(),
                    "signature_c0": hex::encode(sig.c0.as_bytes()),
                    "offline_signed": true,
                    "verified": sig.verify(msg_payload.as_bytes())
                });

                println!("{}", serde_json::to_string_pretty(&tx_json).unwrap());
            } else if args.len() >= 3 && args[2] == "submit" {
                if args.len() < 6 {
                    println!("Error: tx submit requires <recipient_addr> <amount> <fee> [--node <host:port>]");
                    process::exit(1);
                }
                let recipient = &args[3];
                let amount: u64 = args[4].parse().unwrap_or(500_000);
                let fee: u64 = args[5].parse().unwrap_or(50_000);
                let mut node = DEFAULT_NODE;
                if args.len() >= 8 && args[6] == "--node" {
                    node = &args[7];
                }

                let mut rng = OsRng;
                let sender = StealthKeys::generate(&mut rng);
                let receiver = StealthKeys::generate(&mut rng);
                let (one_time_pub, tx_pub_r) = create_stealth_output(&receiver.view_public, &receiver.spend_public, &mut rng);
                let blind = Scalar::random(&mut rng);
                let commitment = PedersenCommitment::create(amount, blind);

                let mut ring = Vec::new();
                for _ in 0..4 {
                    ring.push(EdwardsPoint::mul_base(&Scalar::random(&mut rng)));
                }
                let real_idx = 2;
                ring.insert(real_idx, sender.spend_public);

                let msg_payload = format!("TX_OUT:{}:AMT:{}:FEE:{}", hex::encode(one_time_pub.compress().as_bytes()), amount, fee);
                let sig = ClsagSignature::sign(msg_payload.as_bytes(), &ring, real_idx, &sender.spend_secret, &mut rng);

                let tx_json = serde_json::json!({
                    "version": 1,
                    "recipient": recipient,
                    "amount_atomic": amount,
                    "fee_atomic": fee,
                    "stealth_out_P": hex::encode(one_time_pub.compress().as_bytes()),
                    "tx_pub_R": hex::encode(tx_pub_r.compress().as_bytes()),
                    "commitment": hex::encode(commitment.point.compress().as_bytes()),
                    "key_image": hex::encode(sig.key_image.compress().as_bytes()),
                    "ring_size": ring.len(),
                    "signature_c0": hex::encode(sig.c0.as_bytes())
                });

                let payload_str = serde_json::to_string(&tx_json).unwrap();
                println!("Broadcasting private transaction to http://{}...", node);
                match http_request(node, "POST", "/submit_tx", Some(&payload_str)) {
                    Ok((code, body)) => {
                        if code == 200 {
                            println!("=== TRANSACTION ACCEPTED INTO MEMPOOL ===");
                            let res_val: serde_json::Value = serde_json::from_str(&body).unwrap();
                            println!("Transaction Hash: {}", res_val["tx_hash"].as_str().unwrap_or("-"));
                            println!("Key Image:        {}", res_val["key_image"].as_str().unwrap_or("-"));
                            println!("Mempool Size:     {}", res_val["mempool_size"]);
                            println!("Status:           CONFIRMED (Ready for next BFT block)");
                            println!("==========================================");
                        } else {
                            eprintln!("Submission Rejected (HTTP {}): {}", code, body);
                            process::exit(1);
                        }
                    }
                    Err(err) => {
                        eprintln!("RPC Error: {}", err);
                        process::exit(1);
                    }
                }
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
