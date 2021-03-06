# Copyright 2018 The Cirq Developers
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from typing import Optional

from cirq import ops, decompositions, protocols
from cirq.circuits.circuit import Circuit
from cirq.circuits.optimization_pass import (
    PointOptimizationSummary,
    PointOptimizer,
)


class ConvertToCzAndSingleGates(PointOptimizer):
    """Attempts to convert strange multi-qubit gates into CZ and single qubit
    gates.

    First, checks if the operation has a unitary effect. If so, and the gate is
        a 1-qubit or 2-qubit gate, then performs circuit synthesis of the
        operation.

    Second, attempts to `cirq.decompose` to the operation.

    Third, if ignore_failures is set, gives up and returns the gate unchanged.
        Otherwise raises a TypeError.
    """

    def __init__(self,
                 ignore_failures: bool = False,
                 allow_partial_czs: bool = False) -> None:
        """
        Args:
            ignore_failures: If set, gates that fail to convert are forwarded
                unchanged. If not set, conversion failures raise a TypeError.
            allow_partial_czs: If set, the decomposition is permitted to use
                gates of the form `cirq.CZ**t`, instead of only `cirq.CZ`.
        """
        super().__init__()
        self.ignore_failures = ignore_failures
        self.allow_partial_czs = allow_partial_czs

    def _convert_one(self, op: ops.Operation) -> ops.OP_TREE:
        # Check if this is a CZ
        # Only keep partial CZ gates if allow_partial_czs
        if (isinstance(op, ops.GateOperation)
                and isinstance(op.gate, ops.CZPowGate)
                and (self.allow_partial_czs or op.gate.exponent == 1)):
            return op

        # Measurement?
        if ops.MeasurementGate.is_measurement(op):
            return op

        # Known matrix?
        mat = protocols.unitary(op, None)
        if mat is not None and len(op.qubits) == 1:
            return op
        if mat is not None and len(op.qubits) == 2:
            return decompositions.two_qubit_matrix_to_operations(
                op.qubits[0],
                op.qubits[1],
                mat,
                allow_partial_czs=False)

        # Provides a decomposition?
        decomposed = protocols.decompose_once(op, None)
        if decomposed is not None:
            return decomposed

        # Just let it be?
        if self.ignore_failures:
            return op

        raise TypeError("Don't know how to work with {!r}. "
                        "It isn't composite or an operation with a "
                        "known unitary effect on 1 or 2 qubits.".format(op))

    def convert(self, op: ops.Operation) -> ops.OP_TREE:
        converted = self._convert_one(op)
        if converted is op:
            return converted
        return [self.convert(e) for e in ops.flatten_op_tree(converted)]

    def optimization_at(self, circuit: Circuit, index: int, op: ops.Operation
                        ) -> Optional[PointOptimizationSummary]:
        converted = self.convert(op)
        if converted is op:
            return None

        return PointOptimizationSummary(
            clear_span=1,
            new_operations=converted,
            clear_qubits=op.qubits)
