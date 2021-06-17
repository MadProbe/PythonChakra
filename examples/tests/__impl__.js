export class Tests {
    static run(name, obj) {
        for (const key in obj) {
            if ({}.hasOwnProperty.call(obj, key)) {
                try {
                    obj[key].call(obj);
                } catch (error) {
                    console.error(`Test ${ name } - "${ key }" failed!:`, error instanceof Error ? error.stack : error);
                }
            }
        }
    }
}

export class AssertionError extends Error { }

export const assert = (condition, error) => {
    if (!condition) {
        throw new AssertionError(error);
    }
};

export const assertNot = (condition, error) => {
    if (condition) {
        throw new AssertionError(error);
    }
};

/**
 * 
 * @param {any} value 
 * @param {"string" | "number" | "bigint" | "boolean" | "symbol" | "undefined" | "object" | "function"} type 
 * @param {any} error 
 */
export const assertType = (value, type, error) => {
    if (typeof value !== type) {
        throw new AssertionError(error);
    }
};
