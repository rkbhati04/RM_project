# The First Research Paper: Encrypted DNS => Privacy?

**Paper:** *Encrypted DNS => Privacy? A Traffic Analysis Perspective*  
**Authors:** Sandra Siby, Marc Juarez, Claudia Diaz, Narseo Vallina-Rodriguez, and Carmela Troncoso  
**Source:** [24301.pdf](../24301.pdf)

## The Story

Imagine Alice visiting a website. Before the website opens, her device asks DNS a simple question: "What is the network address of this domain?" Traditional DNS sends that question in the clear. Anyone watching the network can read the domain name, record it, redirect it, or block it.

Encrypted DNS was created to close that obvious window. With DNS-over-HTTPS (DoH) or DNS-over-TLS (DoT), the question and answer are hidden inside encryption. It is tempting to conclude that the observer now sees nothing useful.

This paper asks the uncomfortable next question: **even if the words are hidden, can the shape of the conversation reveal the answer?**

The observer cannot read the DNS message, but can still notice things such as:

- how many packets are exchanged;
- how large the packets are;
- which direction the packets travel;
- how quickly packets arrive;
- how the packets form short bursts.

Those visible measurements become a kind of silhouette. Different domains often produce different DNS answers, and different answers create different traffic silhouettes. The observer does not need to read the label on the package if the package shape is distinctive enough.

## The Investigator's Method

The researchers model a **passive adversary** positioned between the user and the DNS resolver. The adversary does not decrypt traffic or modify it. The goal is to infer which domain the user queried, either for surveillance or censorship.

The first important discovery is that ordinary website-fingerprinting features are not enough. Web traffic is large and long-lived; DNS traffic is usually made of small, short, bursty exchanges. Therefore, the researchers design a new feature set specifically for encrypted DNS, focusing on local packet sizes, directions, timing, and short sequences.

They test the attack in two situations:

1. **Closed world:** the attacker already knows the list of possible domains and must choose one of them.
2. **Open world:** the attacker monitors a target set while other, unknown domains also appear as background traffic.

This distinction matters. Closed-world accuracy shows whether fingerprints are learnable under controlled conditions. Open-world performance is closer to the messier world outside the laboratory.

## What They Discover

The first shock is that encrypted DNS is still fingerprintable. The researchers identify domains with high accuracy in both closed- and open-world settings. In other words, encryption protects the content of the DNS message, but it does not automatically erase the metadata around the message.

The second shock is efficiency. The paper reports that its attack needs **124 times less data** than attacks against HTTPS flows. DNS conversations are small, so a surprisingly small amount of traffic can carry a useful fingerprint.

The attack is not equally strong everywhere. The researchers vary factors such as the user's location, recursive resolver, operating platform, and DNS client. These factors reduce accuracy because they change the traffic shape. However, they do not eliminate the attack. The lesson is that environmental variation makes recognition harder, but does not guarantee privacy.

The paper also examines censorship. A censor does not necessarily need to read a domain name directly. If the traffic pattern is distinctive enough, the censor can classify the encrypted DNS exchange and block or interfere with it. Thus, encrypted DNS can prevent simple text inspection while still leaving room for traffic-analysis-based censorship.

## Why Padding Does Not Save the Day

Padding adds extra bytes to make messages look less distinctive. The paper evaluates standardized padding schemes and finds that they are **not effective enough** against the proposed traffic-analysis attacks.

The reason is important to remember: padding may change packet size, but a fingerprint can also use timing, direction, packet sequences, and burst structure. Hiding one clue does not necessarily hide the whole silhouette.

## The Stronger Defense in This Paper

The researchers find that **Tor is a good defense against DoH traffic analysis**. Tor was not originally designed as a perfect defense against website fingerprinting, but its relaying and traffic-mixing behavior makes the encrypted DNS conversation less directly tied to the user's local network view.

This does not mean Tor solves every privacy problem. It means that simply encrypting DNS is a weaker defense than placing the traffic inside a system that also obscures the observable communication pattern.

## The Main Lesson

The paper separates two ideas that are easy to confuse:

- **Content confidentiality:** an observer cannot read the DNS name inside the encrypted message.
- **Traffic-analysis resistance:** an observer cannot infer the DNS name from visible metadata.

Encrypted DNS succeeds at the first goal, but by itself does not fully achieve the second. Privacy is not only about hiding the words. It is also about hiding the shape, rhythm, and size of the conversation carrying those words.

## Connection to Our Project

This paper is the foundation for the project in this repository. Our experiments extend the same question to modern encrypted DNS transports: DoH and DoH/3.

The project measures metadata such as packet counts, packet sizes, byte totals, inter-arrival times, burst behavior, and the signed sizes of the first packets. The later results support the first paper's central warning: protocol and domain information can remain visible through traffic shape even when the payload is encrypted.

There is also an important difference. The paper studies DoH and DoT, while our project compares standard DoH with the newer QUIC-based DoH/3 transport. Therefore, our results should be understood as an extension of the paper's question, not as numbers that belong to the original paper.

## Memory Card

**Problem:** Encrypted DNS hides the domain name, but may reveal its traffic silhouette.  
**Attacker:** A passive observer who sees packet metadata but cannot decrypt payloads.  
**Method:** DNS-specific traffic features plus domain-fingerprinting attacks.  
**Findings:** High-accuracy identification, 124x less data than HTTPS attacks, censorship remains possible, and standardized padding is insufficient.  
**Defense:** Tor substantially weakens the direct traffic-analysis view.  
**Core idea:** Encryption hides *what was said*; privacy also requires hiding *how the conversation looked*.

## One-Sentence Recall

**The paper shows that encrypted DNS can hide the domain name while still leaving a recognizable fingerprint in packet sizes, timing, direction, and bursts.**
