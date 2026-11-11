# Speech for Research Paper 1 Slide

Good morning everyone.

This slide summarizes the first research paper by Siby and colleagues, published at NDSS in 2020. The paper studies whether encrypted DNS-over-HTTPS, or DoH, really prevents an observer from identifying the websites a user visits.

The researchers used Cloudflare and Google as DoH resolvers and built a dataset containing 1,500 websites selected from the Alexa website ranking. They collected traffic from multiple locations and with different clients, because traffic patterns can change across environments.

Instead of reading the encrypted DNS content, they examined metadata that remains visible. Their features included TLS record-size sequences, represented as n-grams, and patterns of packet bursts. They then used a Random Forest classifier with 10-fold cross-validation to identify the queried website.

The results show that encrypted DNS is not automatically resistant to traffic analysis. In a closed-world experiment, the classifier achieved an F1-score of approximately 0.87 to 0.90. This means that, when the possible websites are known in advance, the traffic patterns contain enough information to identify the website with high accuracy.

However, the attack became much weaker when the environment changed. This shows that location, client, and resolver conditions affect the fingerprint. The researchers also tested EDNS0 padding. Padding reduced the attack performance to about 0.45 F1, but it did not completely remove the leakage.

The paper found that DNS-over-Tor was the only fully effective defense in their experiments, because it hides the direct relationship between the user and the DoH traffic pattern more effectively.

The main limitation, and the research gap relevant to our work, is that this study tested DoH only. It did not test DNS-over-HTTP/3, or DoH/3. Therefore, our research extends this work by asking whether the newer HTTP/3 and QUIC-based transport provides better protection against website fingerprinting.

To summarize: DoH encrypts the DNS content, but packet sizes and burst patterns can still reveal information. This paper establishes the fingerprinting problem, while our work investigates whether DoH/3 changes that result.

Thank you.
