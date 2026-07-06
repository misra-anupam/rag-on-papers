# Observations on embeddings

Embedding choice and chunk strategy are the highest levers

## RoPE

Problems with original Transformers paper PE:
* Additive in nature to the text embedding, effect is lost/minimized after attention computation
* Does not generalize over lengths

RoPE:

* For every pair of dims, a rotation matrix R(theta) is calculated
[
    cos (m*theta_i)   -sin (m*theta_i)
    sin (m*theta_i)   cos (m*theta_i)
]

theta_i = 10000^(-2*i/d)
For each pair of dims theta_i is same, theta moves slower for higher dims and faster for lower dims


* R(theta_i) matrix
[
    R(theta) 0 ... 0
    0        R(theta)
    0        0 ... R(theta(d/2-1))
]

* Query at pos m is multiplied with key at pos n, and the effective angle becomes (n-m);
  hence the relative position informations are used in the attention calculation directly
