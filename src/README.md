README file for Updated Infection Model 

<table>
  <thead>
    <tr>
      <th>Parameter</th>
      <th>Meaning</th>
      <th>Source</th>
      <th>Default Value</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>R<sub>0</sub></td>
      <td>Upper limit of virions to get infected</td>
      <td>Calculated in infection model</td>
      <td>900 copies</td>
    </tr>
    <tr>
      <td>R<sub>C</sub></td>
      <td>Inhaled virions by an individual</td>
      <td>Calculated in infection model</td>
      <td></td>
    </tr>
    <tr>
        <td>c<sub>v</sub></td>
        <td>Concentration of virions in the environment</td>
        <td>Calculated in the infection model</td>
        <td></td>
    </tr>
    <tr>
        <td>f<sub>inh</sub></td>
        <td>Fraction of virions inhaled by an individual</td>
        <td>Calculated in the infection model</td>
        <td></td>
    </tr>
    <tr>
        <td>t<sub>room</sub></td>
        <td>Duration of exposure</td>
        <td>From the user (assumed)</td>
        <td></td>
    </tr>
    <tr>
        <td>N<sub>close</sub></td>
        <td>Virion dose inhaled given the distance from the infected person</td>
        <td>From the user (assumed)</td>
        <td></td>
    </tr>
    <tr>
        <td>t<sub>close</sub></td>
        <td>Time spent within 2 meters of the infected person</td>
        <td>From the user (assumed)</td>
        <td></td>
    </tr>
    <tr>
        <td>m<sub>filter</sub></td>
        <td>Mask filteration rate</td>
        <td>Getting type of mask from the user and accordingly using default values (assumed)</td>
        <td>0.01 for surgical masks and 0.5 for fabric masks</td>
    </tr>
    <tr>
        <td>a<sub>filter</sub></td>
        <td>Volume of clean air an air filtering system can produce per unit time (in cubic feet per meter)</td>
        <td>From the user (assumed)</td>
        <td></td>
    </tr>
    <tr>
        <td>n</td>
        <td>Number of infectious people</td>
        <td></td>
        <td></td>
    </tr>
    <tr>
        <td>d</td>
        <td>Paricle degradation rate</td>
        <td>Calculated as 1/lifetime</td>
        <td></td>
    </tr>
    <tr>
        <td>lifetime</td>
        <td>Lifetime of the virion</td>
        <td></td>
        <td></td>
    </tr>
    <tr>
        <td>r<sub>i</sub></td>
        <td>rate of emission of person i </td>
        <td></td>
        <td>Estimates for delta variant patients: 3.563 * 10 ^3 to 2.345 * 10^5 copies per minute. <br> Estimates for omicron variant patients: 6.635 * 10^3 to 7.796 * 10^5 copies per minute </td>
    </tr>
    <tr>
        <td>V</td>
        <td>Volume of the facility (in liters)</td>
        <td></td>
        <td></td>
    </tr>
    <tr>
        <td>f<sub>v</sub><sub>i</sub></td>
        <td>Fraction of viruses in droplet size class i</td>
        <td></td>
        <td></td>
    </tr>
    <tr>
        <td>p<sub>i</sub></td>
        <td>Deposition probability for droplet size class i</td>
        <td></td>
        <td></td>
    </tr>
  </tbody>
</table>
