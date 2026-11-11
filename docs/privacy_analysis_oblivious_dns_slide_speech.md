# Speech for the ODoH Research Paper Slide

Good morning everyone.

This slide presents the work of Salari and colleagues, published at the IEEE Dependable Systems and Networks conference in 2025. The paper studies whether Oblivious DNS-over-HTTPS, or ODoH, can protect users from website fingerprinting attacks.

The story begins with the privacy goal of ODoH. ODoH separates the client from the DNS resolver through an oblivious design, so that the resolver should not directly learn the client's identity. However, the researchers ask whether an observer can still identify the requested website by looking at the shape of the encrypted traffic.

To investigate this question, the authors built a testbed on GENI using 10 geographically distributed clients. They tested three public resolvers: Google, Cloudflare, and Quad9. The protocol under study was ODoH. For classification, they used a deep-learning ensemble that combines an FCNN, a CNN, and a GRU. These models capture different kinds of patterns in the traffic, including numerical features, local packet patterns, and sequence behavior.

The first key result is that the attack was highly successful. The model achieved 94.34 percent accuracy in the closed-world setting, with an F1-score of 0.9413. In simple terms, even though ODoH hides the DNS content and separates the client from the resolver, the traffic still contains a strong fingerprint of the website.

The researchers then added 15 percent background traffic to make the situation more realistic. The accuracy dropped by only about three percentage points. This is important because it shows that the attack is not dependent on a perfectly clean laboratory trace. It remains effective even when unrelated traffic is present.

The study also examined environmental changes. Client location affected accuracy by approximately nine percent, while time drift affected it by approximately three percent. This tells us that location is a stronger source of variation than simply collecting the traffic at a different time. However, these changes reduce the attack accuracy rather than eliminating the fingerprint.

Finally, the authors tested a defense that combines padding, fragmentation, and dummy packets. This defense reduced the attack accuracy to approximately seven percent. That is a major improvement because it makes the traffic patterns much less recognizable.

The research gap is shown on the right side of the slide. This study covers ODoH only; it does not test DNS-over-HTTP/3. Therefore, our research extends this work by examining DoH/3 and asking whether its HTTP/3 and QUIC transport changes the amount of metadata leakage.

To conclude, this paper shows that ODoH can hide the direct identity relationship between a client and a resolver, but it does not automatically hide the traffic fingerprint. The attack is strong in the original setting, remains strong with background traffic, and is greatly reduced only when traffic is deliberately padded, fragmented, and mixed with dummy packets.

Thank you.
