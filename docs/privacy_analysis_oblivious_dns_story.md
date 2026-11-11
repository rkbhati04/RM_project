# The Second Research Paper: Privacy Analysis of Oblivious DNS over HTTPS

**Paper:** *Privacy Analysis of Oblivious DNS over HTTPS: a Website Fingerprinting Study*  
**Authors:** Mohammad Amir Salari, Abhinav Kumar, Federico Rinaudi, Reza Tourani, Alessio Sacco, and Flavio Esposito  
**Publication:** 2025 IEEE/IFIP International Conference on Dependable Systems and Networks  
**Source:** [Privacy_Analysis_of_Oblivious_DNS_over_HTTPS_a_Website_Fingerprinting_Study.pdf](../Privacy_Analysis_of_Oblivious_DNS_over_HTTPS_a_Website_Fingerprinting_Study.pdf)

## The Story

Imagine a user asking for the address of a website. In ordinary encrypted DNS, the user connects to a resolver through DoH or DoT. The message is encrypted, but the resolver and an observer may still learn useful information from the connection and its traffic pattern.

Oblivious DNS-over-HTTPS, or **ODoH**, tries to separate those identities. The user sends an encrypted DNS request through a proxy. The proxy can see where the request comes from, but it should not see the DNS content. The target resolver can answer the DNS request, but it should not see the user's original IP address. In the ideal story, no single party sees both **who asked** and **what domain was requested**.

The researchers ask a harder question: **even if ODoH separates the user's identity from the resolver, can a passive observer still recognize the website from the shape of the traffic?**

The observer does not need to decrypt the DNS request. Packet sizes, packet timing, direction, and bursts can form a recognizable pattern. This is called **website fingerprinting**.

## The Experiment

The researchers build an ODoH testbed on **GENI**, a research network that allows experiments from different locations. They collect ODoH traffic traces and study the problem in an **open-world setting**.

Open world means that the attacker is not limited to a small, perfectly known list of websites. There are target websites the attacker cares about, but other websites can appear as background or non-target traffic. This is more realistic than a closed-world experiment where every possible website is already known.

For analysis, the researchers use deep-learning-based techniques, including ensemble learning. The model learns the relationship between observable traffic patterns and the website that produced them. The attack uses metadata rather than the plaintext DNS content.

## The Main Discovery

The paper reports that a passive adversary can identify targeted websites from ODoH traces with **94% accuracy**.

This is the surprising part of the story. ODoH improves privacy by hiding the user's identity from the resolver, but that identity separation does not automatically erase the traffic fingerprint. The observer may still recognize the conversation's shape and infer the website being requested.

So ODoH protects one privacy relationship very well:

- the resolver should not directly learn the client's IP address;
- the proxy should not learn the DNS request content.

But the paper shows that another relationship remains vulnerable:

- the traffic observer may infer the requested website from metadata.

## What Changes the Attack?

The researchers examine several factors that affect fingerprinting performance:

- **Client location:** network conditions and paths can change packet timing and patterns.
- **Available resolver:** different resolver implementations can produce different fingerprints.
- **Time stability:** a fingerprint that works at one time may change as network conditions or service behavior change.

These factors influence the attack's success, but they do not make the privacy problem disappear. They show that a fingerprint is not always universal. It can be strong in one environment and weaker in another, while still being useful to an attacker who understands the target environment.

## The Attempted Solution

The paper does not stop after demonstrating the attack. The researchers prototype a mitigation strategy designed to make ODoH traces less distinctive. The goal is to reduce the useful differences between websites, so that the attacker sees many conversations with similar shapes instead of one recognizable pattern per website.

Their evaluation demonstrates that the proposed mitigation improves client privacy against the fingerprinting attack. The broader lesson is that ODoH needs traffic-shaping or similar protections in addition to identity separation if it is expected to resist metadata analysis.

## Why This Paper Matters

The paper teaches us that privacy has layers. ODoH addresses the identity-linking problem by dividing responsibility between a proxy and a target resolver. However, encryption and proxying alone do not guarantee traffic-analysis resistance.

The paper also demonstrates why open-world evaluation is important. A method that performs well only when every possible website is known may not represent a real attack. By testing in the open world, the researchers ask whether target websites can still be recognized among unrelated traffic.

## Connection to Our Research

The second paper is related to our project because both studies examine website fingerprinting from encrypted DNS metadata. The difference is the protocol being studied:

- **This paper:** Oblivious DNS-over-HTTPS, or ODoH.
- **Our project:** DoH and DoH/3, with special attention to DoH/3.

The second paper focuses on whether ODoH's proxy-based privacy design withstands website fingerprinting. Our project focuses on how transport choices and resolver behavior affect the leakage signal. Together, they support the same general warning: protecting DNS content or separating identities is not enough unless the visible traffic pattern is also made difficult to recognize.

## Memory Card

**Problem:** ODoH hides the direct link between the client and the resolver, but traffic metadata may still reveal the website.  
**Privacy design:** A proxy hides the client's identity from the target resolver, while encryption hides the DNS request from the proxy.  
**Attack:** Passive website fingerprinting using encrypted traffic traces.  
**Setting:** Open world, with data collected on the GENI research network.  
**Model:** Deep-learning methods, including ensemble learning.  
**Main result:** Targeted websites were identified with 94% accuracy.  
**Mitigation:** Traffic-shaping protection reduced the usefulness of fingerprints.  
**Core idea:** ODoH hides who asked, but the traffic shape may still reveal what was asked.

## One-Sentence Recall

**ODoH separates the user from the resolver, but the second paper shows that a passive observer can still recognize the requested website from the encrypted traffic pattern.**
