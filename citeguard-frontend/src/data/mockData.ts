export type Status = 'Supported' | 'Contradicted' | 'Unrelated' | 'Numerical Mismatch';

export interface Claim {
  id: string;
  text: string;
  context: string;
  citationNumber: string;
  sourceDocument: string;
  evidence: string;
  status: Status;
  confidence: number;
  numericalCheck: string | null;
}

export const mockClaims: Claim[] = [
  {
    id: 'c1',
    text: 'Training time was reduced by 40% when utilizing the novel sparse attention mechanism compared to the standard dense transformer baseline.',
    context: 'The efficiency of our proposed architecture is demonstrated in Table 2. Specifically, training time was reduced by 40% when utilizing the novel sparse attention mechanism compared to the standard dense transformer baseline [12], which corroborates earlier findings in sparse attention literature.',
    citationNumber: '[12]',
    sourceDocument: 'Vaswani et al., 2017. Attention Is All You Need. arXiv:1706.03762.',
    evidence: 'In our experiments with sparse attention on the WMT 2014 English-to-German translation task, the model achieved comparable BLEU scores while reducing overall training time by exactly 40% relative to the dense self-attention baseline.',
    status: 'Supported',
    confidence: 94,
    numericalCheck: "Claim: '40%' | Source: '40%' -> Match",
  },
  {
    id: 'c2',
    text: 'Global mean sea level is projected to rise by 2.5 meters by the year 2100 under the RCP8.5 emission scenario.',
    context: 'Coastal vulnerability models must account for extreme bounds of climate projections. Recent IPCC assessments indicate that global mean sea level is projected to rise by 2.5 meters by the year 2100 under the RCP8.5 emission scenario [4], necessitating immediate adaptive infrastructure planning.',
    citationNumber: '[4]',
    sourceDocument: 'IPCC, 2021: Climate Change 2021: The Physical Science Basis.',
    evidence: 'Under the highest emission scenario (RCP8.5), global mean sea level rise is projected to be likely in the range of 0.63–1.01 meters by 2100. A rise approaching 2 meters cannot be ruled out due to deep uncertainty in ice-sheet processes, but 2.5 meters is not supported by current modeling consensus.',
    status: 'Numerical Mismatch',
    confidence: 88,
    numericalCheck: "Claim: '2.5 meters' | Source: '0.63–1.01 meters (up to 2m)' -> Mismatch",
  },
  {
    id: 'c3',
    text: 'The administration of 50mg of Compound X daily showed no statistically significant reduction in systemic inflammation markers after 6 weeks.',
    context: 'Previous pharmacological interventions yielded mixed results. However, in the latest Phase II clinical trial, the administration of 50mg of Compound X daily showed no statistically significant reduction in systemic inflammation markers after 6 weeks [21].',
    citationNumber: '[21]',
    sourceDocument: 'Smith & Jones (2023). Efficacy of Compound X in Autoimmune Disorders. Journal of Medical Research.',
    evidence: 'Over the 6-week trial period, patients receiving a 50mg daily dose of Compound X exhibited a marked, statistically significant decrease (p < 0.01) in key systemic inflammation markers, notably C-reactive protein (CRP) and Interleukin-6 (IL-6), compared to the placebo group.',
    status: 'Contradicted',
    confidence: 97,
    numericalCheck: null,
  },
  {
    id: 'c4',
    text: 'Graph Neural Networks (GNNs) naturally struggle to capture long-range dependencies due to the over-squashing phenomenon.',
    context: 'While structurally expressive, message-passing architectures possess inherent limitations. Graph Neural Networks (GNNs) naturally struggle to capture long-range dependencies due to the over-squashing phenomenon [8], where exponential information is compressed into fixed-size vectors.',
    citationNumber: '[8]',
    sourceDocument: 'Alon and Yahav (2021). On the Bottleneck of Graph Neural Networks and its Practical Implications. ICLR.',
    evidence: 'We demonstrate that the primary bottleneck in standard message-passing GNNs is the over-squashing effect. When the computation graph expands exponentially with depth, the model fails to propagate information across distant nodes without significant loss, directly limiting the capture of long-range dependencies.',
    status: 'Supported',
    confidence: 91,
    numericalCheck: null,
  },
  {
    id: 'c5',
    text: 'The economic impact of the 2008 financial crisis resulted in a 5% contraction of global GDP in the subsequent fiscal year.',
    context: 'Historical precedents of market volatility show varied recovery trajectories. For instance, the economic impact of the 2008 financial crisis resulted in a 5% contraction of global GDP in the subsequent fiscal year [33], a figure that took nearly half a decade to recover.',
    citationNumber: '[33]',
    sourceDocument: 'World Bank Group (2009). Global Economic Prospects: Crisis, Finance, and Growth.',
    evidence: 'The report details the regulatory failures that precipitated the 2008 housing market collapse, emphasizing the lack of oversight in derivative markets and subprime mortgage lending practices.',
    status: 'Unrelated',
    confidence: 82,
    numericalCheck: null,
  }
];
